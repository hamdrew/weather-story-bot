"""Domain model for NWS Weather Stories."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse


def parse_time(value: str) -> datetime:
    """Parse an ISO 8601 timestamp into an aware datetime (naive values are assumed UTC)."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


@dataclass(frozen=True, slots=True)
class Story:
    """One Weather Story as returned by `GET /offices/{id}/weatherstories`."""

    office_id: str
    start_time: datetime
    end_time: datetime
    update_time: datetime
    title: str
    description: str
    alt_text: str
    priority: bool
    order: int
    download: str
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> Story:
        try:
            return cls(
                office_id=data["officeId"],
                start_time=parse_time(data["startTime"]),
                end_time=parse_time(data["endTime"]),
                update_time=parse_time(data["updateTime"]),
                title=data["title"],
                description=data.get("description") or "",
                alt_text=data.get("altText") or "",
                priority=bool(data.get("priority", False)),
                order=int(data["order"]),
                download=data["download"],
                raw=dict(data),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed weather story: {exc!r}") from exc

    @property
    def image_id(self) -> str:
        """The image UUID: the last path segment of the `download` URL."""
        image_id = urlparse(self.download).path.rstrip("/").rpartition("/")[2]
        if not image_id:
            raise ValueError(f"Cannot extract image id from download URL {self.download!r}")
        return image_id
