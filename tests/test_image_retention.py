from base64 import b64encode
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from typing import cast

import httpx
import pytest
from PIL import Image

from weather_story_bot.history import ImageMetadata
from weather_story_bot.image_retention import (
    ImageRetainer,
    ImageRetentionError,
    StagingReconciler,
    _validate_decoded_image,
)


class History:
    def __init__(self) -> None:
        self.committed: list[tuple[object, ...]] = []
        self.invalid: list[tuple[object, ...]] = []
        self.previous: ImageMetadata | None = None
        self.commit_error: OSError | None = None

    def commit_image(self, *args: object) -> ImageMetadata | None:
        if self.commit_error is not None:
            raise self.commit_error
        self.committed.append(args)
        return self.previous

    def mark_image_invalid(self, *args: object) -> None:
        self.invalid.append(args)


class Paginator:
    def __init__(self, s3: "S3") -> None:
        self._s3 = s3

    def paginate(self, **kwargs: object) -> list[dict[str, object]]:
        self._s3.paginator_requests.append(kwargs)
        return self._s3.pages


class S3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}
        self.deleted: list[str] = []
        self.paginator_operation: str | None = None
        self.paginator_requests: list[dict[str, object]] = []
        self.pages: list[dict[str, object]] = [
            {
                "Contents": [
                    {"Key": "staging/old", "LastModified": datetime(2026, 8, 1, tzinfo=UTC)},
                    {"Key": "staging/new", "LastModified": datetime(2026, 8, 16, tzinfo=UTC)},
                ]
            }
        ]

    def put_object(self, **kwargs: object) -> dict[str, object]:
        key = cast(str, kwargs["Key"])
        self.objects[key] = {
            "ContentType": kwargs["ContentType"],
            "ContentLength": len(kwargs["Body"]),  # type: ignore[arg-type]
            "ChecksumSHA256": kwargs["ChecksumSHA256"],
            "Metadata": kwargs["Metadata"],
        }
        return {}

    def head_object(self, **kwargs: object) -> dict[str, object]:
        return self.objects[cast(str, kwargs["Key"])]

    def copy_object(self, **kwargs: object) -> dict[str, object]:
        key = cast(str, kwargs["Key"])
        source = cast(dict[str, str], kwargs["CopySource"])
        self.objects[key] = self.objects[source["Key"]].copy()
        return {}

    def delete_object(self, **kwargs: object) -> dict[str, object]:
        self.deleted.append(kwargs["Key"])  # type: ignore[arg-type]
        return {}

    def get_paginator(self, operation_name: str) -> Paginator:
        self.paginator_operation = operation_name
        return Paginator(self)


def png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 3), "red").save(output, format="PNG")
    return output.getvalue()


def animated_png() -> bytes:
    output = BytesIO()
    first = Image.new("RGB", (2, 3), "red")
    second = Image.new("RGB", (2, 3), "blue")
    first.save(output, format="PNG", save_all=True, append_images=[second])
    return output.getvalue()


def png_with_dimensions(width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("1", (width, height)).save(output, format="PNG")
    return output.getvalue()


def retainer(
    response: httpx.Response, *, s3: S3 | None = None, history: History | None = None
) -> tuple[ImageRetainer, S3, History]:
    storage = s3 or S3()
    durable_history = history or History()
    client = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    return (
        ImageRetainer(
            client,
            storage,
            durable_history,
            bucket="images",
            allowed_hosts={"weather.gov", "*.weather.gov"},
            clock=lambda: 0,
        ),
        storage,
        durable_history,
    )


def test_retains_verified_image_through_staging_then_current_key() -> None:
    worker, s3, history = retainer(
        httpx.Response(200, content=png(), headers={"content-type": "image/png"})
    )

    metadata = worker.retain(
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        url="https://www.weather.gov/image",
    )

    assert metadata.key == "current/MKX/source/revision"
    assert history.committed[0][3] == metadata
    assert s3.objects["staging/MKX/source/revision"]["ChecksumSHA256"] == b64encode(
        sha256(png()).digest()
    ).decode("ascii")
    assert s3.deleted == ["staging/MKX/source/revision"]


def test_download_normalizes_http_failures_to_image_retention_errors() -> None:
    worker, _, _ = retainer(httpx.Response(502))

    with pytest.raises(ImageRetentionError, match="image download failed"):
        worker.download("https://www.weather.gov/image")


def test_replacement_deletes_the_previous_current_image_after_commit() -> None:
    previous = ImageMetadata("current/MKX/source/old", "image/png", 1, "a", 1, 1)
    history = History()
    history.previous = previous
    worker, s3, _ = retainer(
        httpx.Response(200, content=png(), headers={"content-type": "image/png"}), history=history
    )

    worker.retain(
        office_id="MKX",
        source_story_id="source",
        revision_hash="new",
        url="https://www.weather.gov/image",
    )

    assert s3.deleted == ["staging/MKX/source/new", previous.key]


def test_commit_failure_after_promotion_deletes_new_current_object() -> None:
    history = History()
    history.commit_error = OSError("history unavailable")
    worker, s3, _ = retainer(
        httpx.Response(200, content=png(), headers={"content-type": "image/png"}), history=history
    )

    with pytest.raises(ImageRetentionError, match="image retention failed"):
        worker.retain(
            office_id="MKX",
            source_story_id="source",
            revision_hash="revision",
            url="https://www.weather.gov/image",
        )

    assert "current/MKX/source/revision" in s3.deleted
    assert "staging/MKX/source/revision" not in s3.deleted
    assert history.invalid


def test_retention_rejects_an_uploaded_object_with_mismatched_metadata() -> None:
    class CorruptHeadS3(S3):
        def head_object(self, **kwargs: object) -> dict[str, object]:
            head = super().head_object(**kwargs).copy()
            head["ContentLength"] = 0
            return head

    history = History()
    worker, _, _ = retainer(
        httpx.Response(200, content=png(), headers={"content-type": "image/png"}),
        s3=CorruptHeadS3(),
        history=history,
    )

    with pytest.raises(ImageRetentionError, match="image retention failed"):
        worker.retain(
            office_id="MKX",
            source_story_id="source",
            revision_hash="corrupt-upload",
            url="https://www.weather.gov/image",
        )

    assert history.invalid


def test_current_image_deletion_rejects_noncurrent_keys() -> None:
    worker, s3, _ = retainer(
        httpx.Response(200, content=png(), headers={"content-type": "image/png"})
    )
    current = ImageMetadata("current/MKX/source/revision", "image/png", 1, "a", 1, 1)

    worker.delete_current_image(current)

    assert s3.deleted == [current.key]
    with pytest.raises(ValueError, match="current"):
        worker.delete_current_image(ImageMetadata("retained/MKX/source", "image/png", 1, "a", 1, 1))


@pytest.mark.parametrize(
    "url, content_type, content",
    [
        ("http://www.weather.gov/image", "image/png", png()),
        ("https://attacker.example/image", "image/png", png()),
        ("https://www.weather.gov/image", "image/jpeg", png()),
    ],
)
def test_rejects_unsafe_url_or_declared_magic_mismatch(
    url: str, content_type: str, content: bytes
) -> None:
    worker, _, history = retainer(
        httpx.Response(200, content=content, headers={"content-type": content_type})
    )

    with pytest.raises(ImageRetentionError):
        worker.retain(office_id="MKX", source_story_id="source", revision_hash="revision", url=url)
    assert history.invalid


def test_allows_only_safe_redirects_and_reconciles_old_staging_objects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/first":
            return httpx.Response(302, headers={"location": "/second"})
        return httpx.Response(200, content=png(), headers={"content-type": "image/png"})

    s3 = S3()
    history = History()
    worker = ImageRetainer(
        httpx.Client(transport=httpx.MockTransport(handler)),
        s3,
        history,
        bucket="images",
        allowed_hosts={"weather.gov", "*.weather.gov"},
        clock=lambda: 0,
    )
    worker.retain(
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        url="https://weather.gov/first",
    )

    deleted = StagingReconciler(s3, bucket="images").cleanup(
        older_than=datetime(2026, 8, 8, tzinfo=UTC)
    )
    assert deleted == 1
    assert "staging/old" in s3.deleted


def test_rejects_redirect_loops_and_downloads_that_exceed_the_time_limit() -> None:
    redirect_worker, _, redirect_history = retainer(
        httpx.Response(302, headers={"location": "/again"})
    )

    with pytest.raises(ImageRetentionError, match="image retention failed"):
        redirect_worker.retain(
            office_id="MKX",
            source_story_id="source",
            revision_hash="redirect-loop",
            url="https://www.weather.gov/image",
        )
    assert redirect_history.invalid

    timeout_values = iter((0.0, 21.0))
    timeout_worker = ImageRetainer(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, content=png(), headers={"content-type": "image/png"}
                )
            )
        ),
        S3(),
        History(),
        bucket="images",
        allowed_hosts={"weather.gov", "*.weather.gov"},
        clock=lambda: next(timeout_values),
    )

    with pytest.raises(ImageRetentionError, match="image retention failed"):
        timeout_worker.retain(
            office_id="MKX",
            source_story_id="source",
            revision_hash="timed-out",
            url="https://www.weather.gov/image",
        )


@pytest.mark.parametrize(
    "content",
    [
        animated_png(),
        png_with_dimensions(5001, 5000),
        png_with_dimensions(41, 2),
    ],
)
def test_rejects_animated_oversized_and_extreme_aspect_ratio_images(content: bytes) -> None:
    worker, _, history = retainer(
        httpx.Response(200, content=content, headers={"content-type": "image/png"})
    )

    with pytest.raises(ImageRetentionError, match="image retention failed"):
        worker.retain(
            office_id="MKX",
            source_story_id="source",
            revision_hash="unsafe-image",
            url="https://www.weather.gov/image",
        )
    assert history.invalid


def test_decoder_requires_the_expected_image_format() -> None:
    with pytest.raises(ImageRetentionError, match="decoder type mismatch"):
        _validate_decoded_image(png(), "image/jpeg")


def test_reconciler_processes_every_s3_listing_page() -> None:
    class PagedS3(S3):
        def __init__(self) -> None:
            super().__init__()
            self.pages = [
                {
                    "Contents": [
                        {"Key": "staging/first", "LastModified": datetime(2026, 8, 1, tzinfo=UTC)}
                    ]
                },
                {
                    "Contents": [
                        {"Key": "staging/second", "LastModified": datetime(2026, 8, 1, tzinfo=UTC)}
                    ]
                },
            ]

    s3 = PagedS3()

    deleted = StagingReconciler(s3, bucket="images").cleanup(
        older_than=datetime(2026, 8, 8, tzinfo=UTC)
    )

    assert deleted == 2
    assert s3.deleted == ["staging/first", "staging/second"]
    assert s3.paginator_operation == "list_objects_v2"
    assert s3.paginator_requests == [{"Bucket": "images", "Prefix": "staging/"}]
