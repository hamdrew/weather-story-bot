from datetime import UTC, datetime, timedelta

from weather_story_bot.config import OfficeRegistry
from weather_story_bot.history import (
    ImageMetadata,
    OutcomeCounts,
    PublicationReservation,
    RunStatus,
)
from weather_story_bot.image_retention import ValidatedImage
from weather_story_bot.ingestion import NormalizedCollection, WeatherStory
from weather_story_bot.scheduled_processing import OfficeScheduledProcessor, ScheduledRun
from weather_story_bot.telegram import PublicationResult, TelegramOutcome


def story(**overrides: object) -> WeatherStory:
    return WeatherStory.model_validate(
        {
            "officeId": "MKX",
            "startTime": "2026-08-16T10:00:00Z",
            "endTime": "2026-08-16T18:00:00Z",
            "updateTime": "2026-08-16T11:00:00Z",
            "title": "Heat advisory",
            "description": "Dangerous heat.",
            "altText": "Heat map",
            "priority": True,
            "order": 1,
            "download": "https://www.weather.gov/123e4567-e89b-12d3-a456-426614174000",
        }
        | overrides
    )


class Retriever:
    def __init__(self, collection: NormalizedCollection) -> None:
        self.collection = collection

    def retrieve(
        self, registry: OfficeRegistry, office_id: str, *, processing_deadline: float
    ) -> NormalizedCollection:
        assert office_id == "MKX"
        assert processing_deadline == 840
        return self.collection


class History:
    def __init__(self) -> None:
        self.runs: list[dict[str, object]] = []
        self.deferrals: list[str] = []
        self.expired_offices: list[str] = []
        self.image_hashes: list[str | None] = []
        self.fail_deferral = False

    def put_quarantine(self, run_id: str, item: object) -> None:
        pass

    def put_deferral(self, run_id: str, item: object, reason: str) -> None:
        if self.fail_deferral:
            raise OSError("history unavailable")
        self.deferrals.append(reason)

    def expire_due_stories(self, office_id: str, *, now: datetime | None = None) -> int:
        self.expired_offices.append(office_id)
        return 0

    def observe_story(self, item: object, *, image_sha256: str | None = None) -> tuple[str, bool]:
        self.image_hashes.append(image_sha256)
        return "d" * 64, True

    def get_current_story(self, office_id: str, source_story_id: str) -> dict[str, object]:
        return {}

    def reserve_publication(self, **kwargs: object) -> PublicationReservation:
        from weather_story_bot.history import PublicationOperation, PublicationReservation

        return PublicationReservation(
            "attempt",
            "run",
            "MKX",
            "story",
            "d" * 64,
            PublicationOperation.CREATE,
            "publisher",
            datetime.now(UTC) + timedelta(minutes=1),
        )

    def put_run(self, run_id: str, office_id: str, **kwargs: object) -> None:
        self.runs.append(kwargs)


class Retainer:
    def __init__(self) -> None:
        self.downloads: list[str] = []
        self.retained_images: list[ValidatedImage] = []

    def download(self, url: str) -> ValidatedImage:
        self.downloads.append(url)
        return ValidatedImage(b"image", "image/png", "a" * 64, "checksum", 1, 1)

    def retain(self, *, image: ValidatedImage, **kwargs: object) -> ImageMetadata:
        self.retained_images.append(image)
        return ImageMetadata("current/MKX/story/d", "image/png", 1, "a" * 64, 1, 1)


class Publisher:
    def publish(self, *args: object) -> PublicationResult:
        return PublicationResult(TelegramOutcome.PUBLISHED, message_ref="1")


def registry() -> OfficeRegistry:
    return OfficeRegistry.model_validate(
        {
            "schema_version": 1,
            "offices": [
                {
                    "office_id": "MKX",
                    "weather_stories_url": "https://api.weather.gov/offices/MKX/weatherstories",
                    "display_name": "MKX",
                    "address": {
                        "street_address": "a",
                        "locality": "b",
                        "region": "WI",
                        "postal_code": "1",
                    },
                    "coordinates": {"latitude": 43.04, "longitude": -88.46},
                    "timezone": "America/Chicago",
                    "telegram_channel_id": "mock:mkx",
                    "active": True,
                }
            ],
        }
    )


def test_processor_orders_priority_and_persists_story_cap_deferrals() -> None:
    stories = tuple(
        story(
            order=index,
            priority=index == 2,
            download=f"https://www.weather.gov/{index:08d}-e89b-12d3-a456-426614174000",
        )
        for index in range(26)
    )
    history = History()
    processor = OfficeScheduledProcessor(
        registry(),
        Retriever(NormalizedCollection("MKX", stories, ())),
        history,
        Retainer(),
        Publisher(),
        clock=lambda: 0,
        wall_clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        run_id_factory=lambda: "run",
    )

    result = processor.process_office("MKX")

    assert result.status is RunStatus.SUCCESS_WITH_DEFERRED
    assert result.counts == OutcomeCounts(discovered=26, published=25, deferred=1)
    assert history.deferrals == ["story_cap"]
    assert history.runs[-1]["required_work_completed"] is True


def test_processor_persists_failed_ambiguous_outcome_and_returns_normally() -> None:
    class AmbiguousPublisher(Publisher):
        def publish(self, *args: object) -> PublicationResult:
            return PublicationResult(TelegramOutcome.AMBIGUOUS)

    history = History()
    processor = OfficeScheduledProcessor(
        registry(),
        Retriever(NormalizedCollection("MKX", (story(),), ())),
        history,
        Retainer(),
        AmbiguousPublisher(),
        clock=lambda: 0,
        wall_clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        run_id_factory=lambda: "run",
    )

    result = processor.process_office("MKX")

    assert result.status is RunStatus.FAILED
    assert result.counts.ambiguous == 1
    assert history.runs[-1]["failure_reasons"] == ("publication_ambiguous",)


def test_processor_expires_due_state_and_does_not_publish_an_expired_story() -> None:
    history = History()
    retainer = Retainer()
    processor = OfficeScheduledProcessor(
        registry(),
        Retriever(NormalizedCollection("MKX", (story(endTime="2025-01-01T00:00:00Z"),), ())),
        history,
        retainer,
        Publisher(),
        clock=lambda: 0,
        wall_clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        run_id_factory=lambda: "run",
    )

    result = processor.process_office("MKX")

    assert result == ScheduledRun("run", RunStatus.SUCCESS, OutcomeCounts(discovered=1), True)
    assert history.expired_offices == ["MKX"]
    assert retainer.downloads == []


def test_processor_hashes_downloaded_image_bytes_before_observing_a_story() -> None:
    history = History()
    retainer = Retainer()
    processor = OfficeScheduledProcessor(
        registry(),
        Retriever(NormalizedCollection("MKX", (story(),), ())),
        history,
        retainer,
        Publisher(),
        clock=lambda: 0,
        wall_clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        run_id_factory=lambda: "run",
    )

    processor.process_office("MKX")

    assert history.image_hashes == ["a" * 64]
    assert len(retainer.downloads) == len(retainer.retained_images) == 1


def test_processor_persists_a_failed_run_when_deferral_persistence_fails() -> None:
    history = History()
    history.fail_deferral = True
    stories = tuple(
        story(download=f"https://www.weather.gov/{index:08d}-e89b-12d3-a456-426614174000")
        for index in range(26)
    )
    processor = OfficeScheduledProcessor(
        registry(),
        Retriever(NormalizedCollection("MKX", stories, ())),
        history,
        Retainer(),
        Publisher(),
        clock=lambda: 0,
        wall_clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        run_id_factory=lambda: "run",
    )

    result = processor.process_office("MKX")

    assert result.status is RunStatus.FAILED
    assert history.runs[-1]["failure_reasons"] == ("deferral_persistence_failed",)
