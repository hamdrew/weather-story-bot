"""Safe, single-photo Telegram Weather Story publishing."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from io import BytesIO
from typing import Any, Protocol, cast

from PIL import Image, UnidentifiedImageError
from regex import findall

from weather_story_bot.history import (
    AttemptState,
    ImageMetadata,
    PublicationOperation,
    PublicationReservation,
)
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


class TelegramOutcome(StrEnum):
    """The safe delivery outcomes understood by the publisher."""

    PUBLISHED = "published"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


class TelegramDefinitiveError(TelegramPublicationError):
    """Telegram rejected a request before accepting it."""

    def __init__(
        self,
        message: str,
        *,
        response_metadata: Mapping[str, object],
        retry_after_seconds: float | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.response_metadata = dict(response_metadata)
        self.retry_after_seconds = retry_after_seconds
        self.retryable = retryable


class TelegramAmbiguousError(TelegramPublicationError):
    """The request outcome cannot establish whether Telegram accepted it."""


@dataclass(frozen=True)
class PublicationResult:
    """The durable result of one reservation's single Telegram call."""

    outcome: TelegramOutcome
    message_ref: str | None = None
    response_metadata: dict[str, str] | None = None
    retry_after_seconds: float | None = None
    retryable: bool = False
    retry_deferred: bool = False


def classify_telegram_response(response: Mapping[str, object]) -> tuple[bool, dict[str, str]]:
    """Classify a Telegram response without retaining raw bodies or descriptions."""
    ok = response.get("ok")
    if ok is True:
        return True, _response_metadata(response)
    if ok is not False:
        raise TelegramAmbiguousError("Telegram response did not contain a boolean ok field")
    error_code = response.get("error_code")
    if not isinstance(error_code, int) or isinstance(error_code, bool):
        raise TelegramAmbiguousError("Telegram rejection did not contain an integer error code")
    metadata = _response_metadata(response)
    if error_code == 429:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            metadata["retry_after_seconds"] = str(retry_after)
        return False, metadata
    return False, metadata


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
        _raise_for_telegram_rejection(response)
        message_id = _message_id(response)
        if not isinstance(message_id, (str, int)):
            raise TelegramPublicationError("Telegram send response lacks message_id")
        return str(message_id)
    if reservation.operation is PublicationOperation.EDIT:
        if not reservation.target_message_ref:
            raise TelegramPublicationError("edit reservation lacks a message reference")
        response = telegram.edit_message_media(
            chat_id=channel_id,
            message_id=reservation.target_message_ref,
            media={
                "type": "photo",
                "media": ("weather-story", data, image.content_type),
                "caption": caption.text,
                "caption_entities": list(caption.entities),
            },
        )
        _raise_for_telegram_rejection(response)
        return reservation.target_message_ref
    raise TelegramPublicationError("unsupported publication operation")


def execute_reserved_publication(
    history: Any,
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
) -> PublicationResult:
    """Execute exactly one Telegram call for an already acquired reservation."""
    if not history.start_publication_send(reservation):
        return PublicationResult(TelegramOutcome.AMBIGUOUS)
    try:
        message_ref = publish_photo(
            telegram,
            images,
            bucket=bucket,
            channel_id=channel_id,
            reservation=reservation,
            image=image,
            title=title,
            description=description,
            alt_text=alt_text,
        )
    except TelegramDefinitiveError as error:
        history.transition_publication(
            reservation,
            AttemptState.REJECTED,
            response_metadata=error.response_metadata,
            error_class="telegram_rejected",
        )
        return PublicationResult(
            TelegramOutcome.REJECTED,
            response_metadata={str(k): str(v) for k, v in error.response_metadata.items()},
            retry_after_seconds=error.retry_after_seconds,
            retryable=error.retryable,
        )
    except TelegramPublicationError:
        history.transition_publication(
            reservation, AttemptState.REJECTED, error_class="publication_validation_failed"
        )
        return PublicationResult(TelegramOutcome.REJECTED)
    except Exception:
        history.transition_publication(
            reservation, AttemptState.AMBIGUOUS, error_class="telegram_outcome_unknown"
        )
        return PublicationResult(TelegramOutcome.AMBIGUOUS)

    history.transition_publication(
        reservation,
        AttemptState.PUBLISHED,
        message_ref=message_ref,
        response_metadata={"telegram_status": "ok"},
    )
    return PublicationResult(TelegramOutcome.PUBLISHED, message_ref=message_ref)


def publish_with_retries(
    initial: PublicationReservation,
    execute: Callable[[PublicationReservation], PublicationResult],
    reserve_retry: Callable[[PublicationReservation, int], PublicationReservation | None],
    *,
    now: Callable[[], float],
    sleep: Callable[[float], None],
    deadline: float,
    shutdown_reserve: float = 60.0,
    max_retries: int = 2,
) -> PublicationResult:
    """Retry only definitive failures, using a new reservation for every retry."""
    reservation = initial
    result = execute(reservation)
    retry_ordinal = 0
    while (
        result.outcome is TelegramOutcome.REJECTED
        and result.retryable
        and retry_ordinal < max_retries
    ):
        retry_after = result.retry_after_seconds
        delay = retry_after if retry_after is not None else 2**retry_ordinal
        if now() + delay + shutdown_reserve > deadline:
            return PublicationResult(
                outcome=result.outcome,
                message_ref=result.message_ref,
                response_metadata=result.response_metadata,
                retry_after_seconds=result.retry_after_seconds,
                retryable=result.retryable,
                retry_deferred=True,
            )
        sleep(delay)
        retry_ordinal += 1
        next_reservation = reserve_retry(reservation, retry_ordinal)
        if next_reservation is None:
            return result
        reservation = next_reservation
        result = execute(reservation)
    return result


def _raise_for_telegram_rejection(response: Mapping[str, object]) -> None:
    accepted, metadata = classify_telegram_response(response) if "ok" in response else (True, {})
    if accepted:
        return
    error_code = response.get("error_code")
    retry_after = _retry_after_seconds(response) if error_code == 429 else None
    retryable = (error_code == 429 and retry_after is not None) or (
        isinstance(error_code, int) and 500 <= error_code < 600
    )
    raise TelegramDefinitiveError(
        "Telegram rejected the publication",
        response_metadata=metadata,
        retry_after_seconds=retry_after,
        retryable=retryable,
    )


def _message_id(response: Mapping[str, object]) -> object:
    """Read both the test adapter shape and Telegram's nested result shape."""
    if "message_id" in response:
        return response.get("message_id")
    result = response.get("result")
    return result.get("message_id") if isinstance(result, Mapping) else None


def _retry_after_seconds(response: Mapping[str, object]) -> float | None:
    parameters = response.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    value = parameters.get("retry_after")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def _response_metadata(response: Mapping[str, object]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    error_code = response.get("error_code")
    if isinstance(error_code, int) and not isinstance(error_code, bool):
        metadata["http_status"] = str(error_code)
        metadata["telegram_error_code"] = str(error_code)
    description = response.get("description")
    if isinstance(description, str):
        metadata["telegram_error_description"] = description[:256]
    return metadata


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
