"""Bounded, two-phase Weather Story image retention."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, UnidentifiedImageError

from weather_story_bot.history import ImageMetadata

MAX_IMAGE_BYTES = 9 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_DIMENSION_SUM = 10_000
MAX_ASPECT_RATIO = 20
MAX_REDIRECTS = 3
IMAGE_TIMEOUT_SECONDS = 20.0

_MAGIC_TYPES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png"}


class ImageRetentionError(ValueError):
    """Raised when an image cannot safely become a retained reference."""


class S3Client(Protocol):
    """The minimal S3 client API used by the retention workflow."""

    def put_object(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def head_object(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def copy_object(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def delete_object(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def get_paginator(self, operation_name: str) -> S3Paginator: ...


class S3Paginator(Protocol):
    """The paginated S3 listing API used by staging reconciliation."""

    def paginate(self, **kwargs: Any) -> Iterable[Mapping[str, Any]]: ...


class ImageHistory(Protocol):
    """Current-story operations used by image retention."""

    def commit_image(
        self, office_id: str, source_story_id: str, digest: str, image: ImageMetadata
    ) -> ImageMetadata | None: ...

    def mark_image_invalid(
        self, office_id: str, source_story_id: str, digest: str, reason: str
    ) -> None: ...


@dataclass(frozen=True)
class ValidatedImage:
    """Image bytes and verified properties safe to upload."""

    data: bytes
    content_type: str
    sha256_hex: str
    s3_checksum_sha256: str
    width: int
    height: int


class ImageRetainer:
    """Download, verify, promote, and conditionally commit one current story image."""

    def __init__(
        self,
        client: httpx.Client,
        s3: S3Client,
        history: ImageHistory,
        *,
        bucket: str,
        allowed_hosts: Iterable[str],
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._client = client
        self._s3 = s3
        self._history = history
        self._bucket = bucket
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._clock = clock

    def retain(
        self,
        *,
        office_id: str,
        source_story_id: str,
        revision_hash: str,
        url: str,
        image: ValidatedImage | None = None,
    ) -> ImageMetadata:
        """Retain an accepted image, committing its reference only after S3 verification.

        Callers that need the image checksum to derive ``revision_hash`` may supply an
        already validated download, avoiding a second request for the same bytes.
        """
        current_key: str | None = None
        try:
            image = image or self.download(url)
            staging_key = f"staging/{office_id}/{source_story_id}/{revision_hash}"
            current_key = f"current/{office_id}/{source_story_id}/{revision_hash}"
            self._s3.put_object(
                Bucket=self._bucket,
                Key=staging_key,
                Body=image.data,
                ContentType=image.content_type,
                ChecksumSHA256=image.s3_checksum_sha256,
                Metadata={"width": str(image.width), "height": str(image.height)},
            )
            head = self._s3.head_object(Bucket=self._bucket, Key=staging_key)
            self._verify_head(head, image)
            self._s3.copy_object(
                Bucket=self._bucket,
                Key=current_key,
                CopySource={"Bucket": self._bucket, "Key": staging_key},
                ContentType=image.content_type,
                MetadataDirective="COPY",
            )
            current_head = self._s3.head_object(Bucket=self._bucket, Key=current_key)
            self._verify_head(current_head, image)
            metadata = ImageMetadata(
                current_key,
                image.content_type,
                len(image.data),
                image.sha256_hex,
                image.width,
                image.height,
            )
            previous_image = self._history.commit_image(
                office_id, source_story_id, revision_hash, metadata
            )
        except (
            BotoCoreError,
            ClientError,
            httpx.HTTPError,
            ImageRetentionError,
            OSError,
            UnidentifiedImageError,
        ) as error:
            if current_key is not None:
                self._s3.delete_object(Bucket=self._bucket, Key=current_key)
            self._history.mark_image_invalid(office_id, source_story_id, revision_hash, str(error))
            raise ImageRetentionError("image retention failed") from error
        self._s3.delete_object(Bucket=self._bucket, Key=staging_key)
        if previous_image is not None and previous_image.key != metadata.key:
            self._s3.delete_object(Bucket=self._bucket, Key=previous_image.key)
        return metadata

    def delete_current_image(self, image: ImageMetadata) -> None:
        """Delete a no-longer-publishable image from the current-image namespace."""
        if not image.key.startswith("current/"):
            raise ValueError("only current image keys may be deleted")
        self._s3.delete_object(Bucket=self._bucket, Key=image.key)

    def download(self, url: str) -> ValidatedImage:
        """Fetch a small allowed HTTPS image through at most three safe redirects."""
        try:
            return self._download(url)
        except ImageRetentionError:
            raise
        except (httpx.HTTPError, OSError, UnidentifiedImageError) as error:
            raise ImageRetentionError("image download failed") from error

    def _download(self, url: str) -> ValidatedImage:
        """Perform the image download and validation after normalizing caller errors."""
        started = self._clock()
        current_url = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            self._validate_url(current_url)
            with self._client.stream(
                "GET", current_url, follow_redirects=False, timeout=IMAGE_TIMEOUT_SECONDS
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if location is None or redirect_count == MAX_REDIRECTS:
                        raise ImageRetentionError("image redirect policy rejected response")
                    current_url = str(response.url.join(location))
                    continue
                response.raise_for_status()
                declared_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                chunks: list[bytes] = []
                size = 0
                digest = sha256()
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES or self._clock() - started > IMAGE_TIMEOUT_SECONDS:
                        raise ImageRetentionError("image download exceeded its resource limit")
                    digest.update(chunk)
                    chunks.append(chunk)
            data = b"".join(chunks)
            actual_type = _magic_type(data)
            if actual_type is None or declared_type != actual_type:
                raise ImageRetentionError("declared image type did not match image bytes")
            width, height = _validate_decoded_image(data, actual_type)
            raw_digest = digest.digest()
            return ValidatedImage(
                data,
                actual_type,
                raw_digest.hex(),
                b64encode(raw_digest).decode("ascii"),
                width,
                height,
            )
        raise AssertionError("redirect loop must return or raise")

    def _validate_url(self, value: str) -> None:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not _host_allowed(parsed.hostname, self._allowed_hosts)
        ):
            raise ImageRetentionError("image URL is not an allowed HTTPS host")

    @staticmethod
    def _verify_head(head: Mapping[str, Any], image: ValidatedImage) -> None:
        if (
            head.get("ContentType") != image.content_type
            or head.get("ContentLength") != len(image.data)
            or head.get("ChecksumSHA256") != image.s3_checksum_sha256
            or head.get("Metadata", {}).get("width") != str(image.width)
            or head.get("Metadata", {}).get("height") != str(image.height)
        ):
            raise ImageRetentionError("uploaded image did not pass integrity verification")


class StagingReconciler:
    """Delete old uncommitted staging keys; S3 lifecycle remains the safety net."""

    def __init__(self, s3: S3Client, *, bucket: str) -> None:
        self._s3 = s3
        self._bucket = bucket

    def cleanup(self, *, older_than: datetime) -> int:
        """Delete uncommitted staging objects that S3 lists as older than the cutoff."""
        deleted = 0
        paginator = self._s3.get_paginator("list_objects_v2")
        for response in paginator.paginate(Bucket=self._bucket, Prefix="staging/"):
            for item in response.get("Contents", []):
                modified = item.get("LastModified")
                if modified is not None and modified <= older_than:
                    self._s3.delete_object(Bucket=self._bucket, Key=item["Key"])
                    deleted += 1
        return deleted


def _magic_type(data: bytes) -> str | None:
    return next(
        (content_type for prefix, content_type in _MAGIC_TYPES.items() if data.startswith(prefix)),
        None,
    )


def _validate_decoded_image(data: bytes, content_type: str) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as image:
        if image.format not in {"JPEG", "PNG"} or getattr(image, "is_animated", False):
            raise ImageRetentionError("image must be a non-animated JPEG or PNG")
        image.verify()
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
        if width * height > MAX_IMAGE_PIXELS or width + height > MAX_DIMENSION_SUM:
            raise ImageRetentionError("image dimensions exceed the allowed limit")
        if max(width, height) / min(width, height) > MAX_ASPECT_RATIO:
            raise ImageRetentionError("image aspect ratio exceeds the allowed limit")
        if (content_type == "image/jpeg" and image.format != "JPEG") or (
            content_type == "image/png" and image.format != "PNG"
        ):
            raise ImageRetentionError("image decoder type mismatch")
        image.load()
    return width, height


def _host_allowed(host: str, allowlist: frozenset[str]) -> bool:
    host = host.lower().rstrip(".")
    return host in allowlist or any(
        entry.startswith("*.") and host.endswith(entry[1:]) and host != entry[2:]
        for entry in allowlist
    )
