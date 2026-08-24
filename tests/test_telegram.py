from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image
from regex import findall

from weather_story_bot.history import (
    AttemptState,
    ImageMetadata,
    PublicationOperation,
    PublicationReservation,
)
from weather_story_bot.telegram import (
    TELEGRAM_CAPTION_LIMIT,
    PublicationResult,
    TelegramOutcome,
    TelegramPublicationError,
    _truncate_graphemes,
    classify_telegram_response,
    execute_reserved_publication,
    publish_photo,
    publish_with_retries,
    render_caption,
)

UNICODE_CAPTION_TEXT = st.text(max_size=1_500)


def _image_bytes() -> bytes:
    image = Image.new("RGB", (2, 3), color="red")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _reservation(
    operation: PublicationOperation = PublicationOperation.CREATE,
) -> PublicationReservation:
    return PublicationReservation(
        attempt_id="attempt",
        run_id="run",
        office_id="MKX",
        source_story_id="story",
        revision_hash="a" * 64,
        operation=operation,
        reservation_owner="worker",
        lease_expires_at=datetime.now(UTC),
        target_message_ref="99" if operation is PublicationOperation.EDIT else None,
    )


class Images:
    def __init__(self, data: bytes, *, content_type: str = "image/png") -> None:
        self.data = data
        self.content_type = content_type
        self.calls: list[dict[str, object]] = []

    def get_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"Body": BytesIO(self.data), "ContentType": self.content_type}


class Telegram:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_photo(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"message_id": 17}

    def edit_message_media(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {}


class History:
    def __init__(self) -> None:
        self.started = 0
        self.transitions: list[AttemptState] = []

    def start_publication_send(self, reservation: PublicationReservation) -> bool:
        del reservation
        self.started += 1
        return True

    def transition_publication(
        self, reservation: PublicationReservation, state: AttemptState, **kwargs: object
    ) -> bool:
        del reservation, kwargs
        self.transitions.append(state)
        return True


def _metadata(data: bytes) -> ImageMetadata:
    from hashlib import sha256

    return ImageMetadata(
        "current/MKX/story/revision", "image/png", len(data), sha256(data).hexdigest(), 2, 3
    )


def test_publish_sends_exactly_one_photo_with_plain_caption() -> None:
    data = _image_bytes()
    telegram = Telegram()

    assert (
        publish_photo(
            telegram,
            Images(data),
            bucket="images",
            channel_id="channel",
            reservation=_reservation(),
            image=_metadata(data),
            title="*Alert*",
            description="text",
            alt_text="map",
        )
        == "17"
    )

    assert len(telegram.calls) == 1
    assert telegram.calls[0]["caption"] == "*Alert*\ntext\n\nImage description: map"
    assert "parse_mode" not in telegram.calls[0]
    assert telegram.calls[0]["caption_entities"] == [{"type": "bold", "offset": 0, "length": 7}]


def test_telegram_response_classification_keeps_retry_metadata_bounded() -> None:
    retryable, metadata = classify_telegram_response(
        {
            "ok": False,
            "error_code": 429,
            "description": "slow down",
            "parameters": {"retry_after": 3},
        }
    )

    assert retryable is False
    assert metadata == {
        "http_status": "429",
        "telegram_error_code": "429",
        "telegram_error_description": "slow down",
        "retry_after_seconds": "3.0",
    }


def test_execute_reserved_publication_transitions_success_and_calls_telegram_once() -> None:
    data = _image_bytes()
    history = History()
    telegram = Telegram()

    result = execute_reserved_publication(
        history,
        telegram,
        Images(data),
        bucket="images",
        channel_id="channel",
        reservation=_reservation(),
        image=_metadata(data),
        title="Title",
        description="text",
        alt_text="",
    )

    assert result == PublicationResult(TelegramOutcome.PUBLISHED, message_ref="17")
    assert history.started == 1
    assert history.transitions == [AttemptState.PUBLISHED]
    assert len(telegram.calls) == 1


def test_retries_use_new_reservations_and_defer_when_delay_does_not_fit() -> None:
    reservations = [_reservation(), _reservation()]
    executed: list[PublicationReservation] = []
    sleeps: list[float] = []
    outcomes = iter(
        [
            PublicationResult(
                TelegramOutcome.REJECTED,
                retry_after_seconds=10,
                retryable=True,
            ),
            PublicationResult(TelegramOutcome.PUBLISHED, message_ref="17"),
        ]
    )

    def execute(reservation: PublicationReservation) -> PublicationResult:
        executed.append(reservation)
        return next(outcomes)

    result = publish_with_retries(
        reservations[0],
        execute,
        lambda previous, ordinal: reservations[ordinal],
        now=lambda: 0,
        sleep=sleeps.append,
        deadline=100,
    )

    assert result.outcome is TelegramOutcome.PUBLISHED
    assert executed == reservations
    assert sleeps == [10]

    deferred = publish_with_retries(
        reservations[0],
        lambda reservation: PublicationResult(
            TelegramOutcome.REJECTED,
            retry_after_seconds=50,
            retryable=True,
        ),
        lambda previous, ordinal: reservations[1],
        now=lambda: 0,
        sleep=sleeps.append,
        deadline=100,
    )
    assert deferred.retry_deferred is True
    assert sleeps == [10]


def test_publish_edits_the_existing_photo_message() -> None:
    data = _image_bytes()
    telegram = Telegram()

    assert (
        publish_photo(
            telegram,
            Images(data),
            bucket="images",
            channel_id="channel",
            reservation=_reservation(PublicationOperation.EDIT),
            image=_metadata(data),
            title="Title",
            description="text",
            alt_text="",
        )
        == "99"
    )
    assert telegram.calls[0]["message_id"] == "99"
    assert telegram.calls[0]["media"] == {
        "type": "photo",
        "media": ("weather-story", data, "image/png"),
        "caption": "Title\ntext",
        "caption_entities": [{"type": "bold", "offset": 0, "length": 5}],
    }


def test_invalid_retained_image_never_calls_telegram() -> None:
    data = _image_bytes()
    telegram = Telegram()
    with pytest.raises(TelegramPublicationError):
        publish_photo(
            telegram,
            Images(b"bad"),
            bucket="images",
            channel_id="channel",
            reservation=_reservation(),
            image=_metadata(data),
            title="Title",
            description="text",
            alt_text="",
        )
    assert telegram.calls == []


def test_truncated_retained_jpeg_never_calls_telegram() -> None:
    image = Image.new("RGB", (100, 100), color="red")
    output = BytesIO()
    image.save(output, format="JPEG")
    truncated = output.getvalue()[:-10]
    metadata = ImageMetadata(
        "current/MKX/story/revision",
        "image/jpeg",
        len(truncated),
        sha256(truncated).hexdigest(),
        100,
        100,
    )
    telegram = Telegram()

    with pytest.raises(TelegramPublicationError, match="decode"):
        publish_photo(
            telegram,
            Images(truncated, content_type="image/jpeg"),
            bucket="images",
            channel_id="channel",
            reservation=_reservation(),
            image=metadata,
            title="Title",
            description="text",
            alt_text="",
        )

    assert telegram.calls == []


def test_caption_omits_an_overlong_optional_description_and_truncates_grapheme_safely() -> None:
    caption = render_caption("e\u0301", "x" * 1100, "description" * 200)
    assert caption.text.endswith("…")
    assert "Image description:" not in caption.text
    assert len(caption.text.encode("utf-16-le")) // 2 <= 1024


@pytest.mark.parametrize(
    ("images", "metadata"),
    [
        (Images(_image_bytes(), content_type="image/jpeg"), _metadata(_image_bytes())),
        (
            Images(_image_bytes()),
            ImageMetadata("current/MKX/story/revision", "image/png", 1, "a" * 64, 2, 3),
        ),
    ],
)
def test_changed_retained_metadata_never_calls_telegram(
    images: Images, metadata: ImageMetadata
) -> None:
    telegram = Telegram()

    with pytest.raises(TelegramPublicationError):
        publish_photo(
            telegram,
            images,
            bucket="images",
            channel_id="channel",
            reservation=_reservation(),
            image=metadata,
            title="Title",
            description="text",
            alt_text="",
        )

    assert len(images.calls) == 1
    assert telegram.calls == []


def test_create_requires_a_telegram_message_reference() -> None:
    data = _image_bytes()

    class MissingMessageIdTelegram(Telegram):
        def send_photo(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(kwargs)
            return {}

    telegram = MissingMessageIdTelegram()
    with pytest.raises(TelegramPublicationError, match="message_id"):
        publish_photo(
            telegram,
            Images(data),
            bucket="images",
            channel_id="channel",
            reservation=_reservation(),
            image=_metadata(data),
            title="Title",
            description="text",
            alt_text="",
        )
    assert len(telegram.calls) == 1


def test_caption_entity_uses_utf16_length_for_astral_characters() -> None:
    caption = render_caption("🌡️ Heat", "Body", "")

    assert caption.entities == ({"type": "bold", "offset": 0, "length": 8},)


@pytest.mark.parametrize("emoji", ["✈️", "👍🏽", "🇺🇸", "1️⃣", "👩‍👩‍👧‍👦"])
def test_truncation_preserves_extended_grapheme_clusters(emoji: str) -> None:
    text = "a" * 1023 + emoji

    assert _truncate_graphemes(text, 1024) == "a" * 1023 + "…"


@settings(max_examples=150, deadline=None)
@given(title=UNICODE_CAPTION_TEXT, description=UNICODE_CAPTION_TEXT, alt_text=UNICODE_CAPTION_TEXT)
def test_render_caption_preserves_unicode_and_entity_invariants(
    title: str, description: str, alt_text: str
) -> None:
    """Exercise arbitrary Unicode, including combining and emoji sequences, without network I/O."""
    caption = render_caption(title, description, alt_text)
    base = f"{title}\n{description}"
    optional = f"\n\nImage description: {alt_text}" if alt_text else ""

    assert len(caption.text.encode("utf-16-le")) // 2 <= TELEGRAM_CAPTION_LIMIT
    if len((base + optional).encode("utf-16-le")) // 2 <= TELEGRAM_CAPTION_LIMIT:
        assert caption.text == base + optional
    elif len(base.encode("utf-16-le")) // 2 <= TELEGRAM_CAPTION_LIMIT:
        assert caption.text == base
    else:
        assert caption.text.endswith("…")
        emitted = caption.text.removesuffix("…")
        assert emitted == "".join(findall(r"\X", base)[: len(findall(r"\X", emitted))])

    rendered_title = caption.text.split("\n", 1)[0]
    expected_entities = (
        ({"type": "bold", "offset": 0, "length": len(rendered_title.encode("utf-16-le")) // 2},)
        if rendered_title
        else ()
    )
    assert caption.entities == expected_entities
