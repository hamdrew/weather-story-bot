"""Safe, single-photo Telegram Weather Story publishing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Any, Protocol, cast

from PIL import Image, UnidentifiedImageError
from regex import findall

from weather_story_bot.history import ImageMetadata, PublicationOperation, PublicationReservation
from weather_story_bot.image_retention import (
    MAX_ASPECT_RATIO,
    MAX_DIMENSION_SUM,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    _magic_type,
)

TELEGRAM_CAPTION_LIMIT = 1024


class TelegramPublicationError(ValueError):
    """Raised before a Telegram call when retained media is unsafe to publish."""


class RetainedImageStore(Protocol):
    """The small S3 read surface required immediately before publication."""

    def get_object(self, **kwargs: Any) -> Mapping[str, Any]: ...


class TelegramClient(Protocol):
    """Telegram operations permitted to a Weather Story publisher."""

    def send_photo(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def edit_message_media(self, **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class Caption:
    """A caption and explicit bold-title entity, without Telegram parse modes."""

    text: str
    entities: tuple[dict[str, object], ...]


def render_caption(title: str, description: str, alt_text: str) -> Caption:
    """Render a bounded explicit-entity caption, preserving user text literally."""
    base = f"{title}\n{description}"
    optional = f"\n\nImage description: {alt_text}" if alt_text else ""
    text = base + optional if _utf16_length(base + optional) <= TELEGRAM_CAPTION_LIMIT else base
    if _utf16_length(text) > TELEGRAM_CAPTION_LIMIT:
        text = _truncate_graphemes(text, TELEGRAM_CAPTION_LIMIT)
    title_text = text.split("\n", 1)[0]
    entity_length = _utf16_length(title_text)
    entities: tuple[dict[str, object], ...] = ()
    if entity_length:
        entities = ({"type": "bold", "offset": 0, "length": entity_length},)
    return Caption(text=text, entities=entities)


def publish_photo(
    telegram: TelegramClient,
    images: RetainedImageStore,
    *,
    bucket: str,
    channel_id: str,
    reservation: PublicationReservation,
    image: ImageMetadata,
    title: str,
    description: str,
    alt_text: str,
) -> str:
    """Make exactly the reservation's one permitted photo create or edit call.

    All retained bytes are checked again before constructing the Telegram request, so
    corrupt or replaced S3 objects cannot result in a remote call.
    """
    data = _load_and_validate_retained_image(images, bucket=bucket, image=image)
    caption = render_caption(title, description, alt_text)
    if reservation.operation is PublicationOperation.CREATE:
        response = telegram.send_photo(
            chat_id=channel_id,
            photo=("weather-story", data, image.content_type),
            caption=caption.text,
            caption_entities=list(caption.entities),
        )
        message_id = response.get("message_id")
        if not isinstance(message_id, (str, int)):
            raise TelegramPublicationError("Telegram send response lacks message_id")
        return str(message_id)
    if reservation.operation is PublicationOperation.EDIT:
        if not reservation.target_message_ref:
            raise TelegramPublicationError("edit reservation lacks a message reference")
        telegram.edit_message_media(
            chat_id=channel_id,
            message_id=reservation.target_message_ref,
            media={
                "type": "photo",
                "media": ("weather-story", data, image.content_type),
                "caption": caption.text,
                "caption_entities": list(caption.entities),
            },
        )
        return reservation.target_message_ref
    raise TelegramPublicationError("unsupported publication operation")


def _load_and_validate_retained_image(
    images: RetainedImageStore, *, bucket: str, image: ImageMetadata
) -> bytes:
    response = images.get_object(Bucket=bucket, Key=image.key)
    body = response.get("Body")
    if body is None or not hasattr(body, "read"):
        raise TelegramPublicationError("retained image body is unavailable")
    data = body.read()
    if not isinstance(data, bytes):
        raise TelegramPublicationError("retained image body is invalid")
    if len(data) != image.byte_size or len(data) > MAX_IMAGE_BYTES:
        raise TelegramPublicationError("retained image size is invalid")
    if response.get("ContentType", image.content_type).split(";", 1)[0] != image.content_type:
        raise TelegramPublicationError("retained image content type changed")
    if sha256(data).hexdigest() != image.sha256_hex or _magic_type(data) != image.content_type:
        raise TelegramPublicationError("retained image integrity check failed")
    try:
        with Image.open(BytesIO(data)) as decoded:
            if getattr(decoded, "is_animated", False):
                raise TelegramPublicationError("animated retained images are not allowed")
            decoded.verify()
        with Image.open(BytesIO(data)) as decoded:
            width, height = decoded.size
            decoded.load()
    except (OSError, UnidentifiedImageError) as error:
        raise TelegramPublicationError("retained image decode failed") from error
    if (
        width != image.width
        or height != image.height
        or width * height > MAX_IMAGE_PIXELS
        or width + height > MAX_DIMENSION_SUM
        or max(width / height, height / width) > MAX_ASPECT_RATIO
    ):
        raise TelegramPublicationError("retained image dimensions are invalid")
    return data


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _truncate_graphemes(value: str, max_utf16_units: int) -> str:
    """Truncate at conservative grapheme boundaries and append one ellipsis."""
    if _utf16_length(value) <= max_utf16_units:
        return value
    pieces: list[str] = []
    for cluster in _clusters(value):
        if _utf16_length("".join(pieces) + cluster + "…") > max_utf16_units:
            break
        pieces.append(cluster)
    return "".join(pieces) + "…"


def _clusters(value: str) -> list[str]:
    """Return Unicode extended grapheme clusters, including complex emoji sequences."""
    return cast(list[str], findall(r"\X", value))
