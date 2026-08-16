"""Office enrichment and strict, office-scoped Weather Story normalization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from weather_story_bot.config import (
    EnvironmentConfig,
    NWSOfficeSeedSet,
    OfficeCoordinates,
    OfficeRegistry,
    OfficeRegistryRecord,
    PostalAddress,
    derive_timezone,
    weather_stories_url,
)
from weather_story_bot.nws_client import NWS_ACCEPT, NWS_USER_AGENT, NWSCollectionClient

OFFICE_ENDPOINT = "https://api.weather.gov/offices/{office_id}"
PAGINATION_FIELDS = frozenset({"pagination", "next", "nextPage", "cursor", "continuation"})
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
NWS_OFFICE_RESOURCE_PATH = re.compile(r"^/offices/[A-Z]{3}$")


class OfficeEnrichmentError(ValueError):
    """Raised when an NWS office or region response cannot seed a registry entry."""


class CollectionValidationError(ValueError):
    """Raised when a collection envelope cannot be safely treated as complete."""


class Geocoder(Protocol):
    """Geocode the NWS postal address retained in an office registry record."""

    def geocode(self, address: PostalAddress) -> OfficeCoordinates: ...


class SupportsJsonGet(Protocol):
    """Minimal HTTP surface required to enrich the NWS office registry."""

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> httpx.Response: ...


class NWSPostalAddress(BaseModel):
    """The flat JSON-LD postal-address shape returned by an NWS office resource."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    street_address: str = Field(alias="streetAddress", min_length=1)
    locality: str = Field(alias="addressLocality", min_length=1)
    region: str = Field(alias="addressRegion", min_length=1)
    postal_code: str = Field(alias="postalCode", min_length=1)


class NWSOfficeResponse(BaseModel):
    """Supported flat JSON-LD contract for ``GET /offices/{office_id}``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    office_id: Annotated[str, Field(alias="id", pattern=r"^[A-Z]{3}$")]
    name: str = Field(min_length=1)
    address: NWSPostalAddress
    telephone: str | None = None
    email: str | None = None
    same_as: HttpUrl = Field(alias="sameAs")
    nws_region: str = Field(alias="nwsRegion", min_length=1)
    parent_organization: HttpUrl = Field(alias="parentOrganization")

    @field_validator("same_as")
    @classmethod
    def require_https_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("NWS resource URL must use HTTPS")
        return value

    @field_validator("parent_organization", mode="before")
    @classmethod
    def require_nws_regional_office_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            parsed = urlparse(value)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname == "api.weather.gov"
                and parsed.username is None
                and parsed.password is None
                and parsed.port is None
                and not parsed.query
                and not parsed.fragment
                and NWS_OFFICE_RESOURCE_PATH.fullmatch(parsed.path) is not None
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("parentOrganization must be an HTTPS NWS office resource URL")
        return value


class NWSRegionalOfficeResponse(BaseModel):
    """Supported flat JSON-LD contract for an office's regional-office resource."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    office_id: Annotated[str, Field(alias="id", pattern=r"^[A-Z]{3}$")]
    name: str = Field(min_length=1)
    same_as: HttpUrl = Field(alias="sameAs")

    @field_validator("same_as")
    @classmethod
    def require_https_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("NWS resource URL must use HTTPS")
        return value


class NWSWeatherStoryCollectionResponse(BaseModel):
    """Supported collection envelope before independently validating story items."""

    model_config = ConfigDict(extra="allow", frozen=True)

    stories: list[object]

    @model_validator(mode="after")
    def rejects_unsupported_pagination(self) -> NWSWeatherStoryCollectionResponse:
        if self.model_extra is not None and PAGINATION_FIELDS & set(self.model_extra):
            raise ValueError("collection advertises unsupported pagination")
        return self


class WeatherStory(BaseModel):
    """A normalized valid story with a stable office-scoped identity."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    office_id: Annotated[str, Field(alias="officeId", pattern=r"^[A-Z]{3}$")]
    start_time: datetime = Field(alias="startTime")
    end_time: datetime = Field(alias="endTime")
    update_time: datetime = Field(alias="updateTime")
    title: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    alt_text: Annotated[str, Field(alias="altText")]
    priority: StrictBool
    order: StrictInt
    download_url: HttpUrl = Field(alias="download")

    @field_validator("start_time", "end_time", "update_time", mode="before")
    @classmethod
    def require_iso_datetime(cls, value: object) -> object:
        """Reject date-only and numeric values before Pydantic can coerce them."""
        if not isinstance(value, str) or "T" not in value:
            raise ValueError("timestamp must be an ISO-8601 date-time")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("timestamp must be an ISO-8601 date-time") from error
        return parsed

    @property
    def source_story_id(self) -> str:
        """Return the UUID in the download URL's final path segment."""
        final_segment = urlparse(str(self.download_url)).path.rstrip("/").rsplit("/", 1)[-1]
        return str(UUID(final_segment))

    @property
    def canonical_identity(self) -> tuple[str, str]:
        """Return the stable identity only available after successful item validation."""
        return self.office_id, self.source_story_id


def _validate_story_download(story: WeatherStory) -> WeatherStory:
    parsed = urlparse(str(story.download_url))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("download must be an absolute HTTPS URL")
    try:
        UUID(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    except ValueError as error:
        raise ValueError("download final path segment must be a UUID") from error
    return story


@dataclass(frozen=True)
class QuarantinedStoryItem:
    """Bounded item-validation metadata; raw story contents are intentionally omitted."""

    array_index: int
    error_code: str
    affected_field: str
    error_summary: str


@dataclass(frozen=True)
class NormalizedCollection:
    """The independently validated stories and quarantined siblings of one office response."""

    office_id: str
    stories: tuple[WeatherStory, ...]
    quarantined: tuple[QuarantinedStoryItem, ...]


class OfficeRegistrySeeder:
    """Build the all-office registry by verifying NWS office and region resources."""

    def __init__(
        self,
        client: SupportsJsonGet,
        geocoder: Geocoder,
        *,
        timeout_seconds: float = 10.0,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._geocoder = geocoder
        self._timeout_seconds = timeout_seconds
        self._headers = {"Accept": NWS_ACCEPT, "User-Agent": NWS_USER_AGENT}
        if headers is not None:
            self._headers.update(headers)
        self._headers["Accept"] = NWS_ACCEPT
        self._headers["User-Agent"] = NWS_USER_AGENT

    def seed(self, seed_set: NWSOfficeSeedSet, environment: EnvironmentConfig) -> OfficeRegistry:
        """Verify and enrich every seed, activating only configured active offices."""
        records = tuple(
            self._seed_office(office_id, environment) for office_id in seed_set.office_ids
        )
        return OfficeRegistry(schema_version=1, offices=records)

    def _seed_office(self, office_id: str, environment: EnvironmentConfig) -> OfficeRegistryRecord:
        payload = self._get_json(OFFICE_ENDPOINT.format(office_id=office_id), "office")
        office = _validate_source_model(NWSOfficeResponse, payload, "office")
        if office.office_id != office_id:
            raise OfficeEnrichmentError("NWS office response ID did not match the requested office")
        region_payload = self._get_json(str(office.parent_organization), "regional office")
        region = _validate_source_model(
            NWSRegionalOfficeResponse, region_payload, "regional office"
        )
        address = PostalAddress(
            street_address=office.address.street_address,
            locality=office.address.locality,
            region=office.address.region,
            postal_code=office.address.postal_code,
        )
        coordinates = self._geocoder.geocode(address)
        active = office_id in environment.active_office_ids
        return OfficeRegistryRecord(
            office_id=office_id,
            weather_stories_url=HTTP_URL_ADAPTER.validate_python(weather_stories_url(office_id)),
            display_name=office.name,
            address=address,
            coordinates=coordinates,
            timezone=derive_timezone(coordinates),
            telegram_channel_id=environment.office_channels.get(office_id),
            active=active,
            telephone=_optional_string(office.telephone),
            email=_optional_string(office.email),
            office_home_url=office.same_as,
            region_name=region.name,
            region_home_url=region.same_as,
        )

    def _get_json(self, url: str, resource_name: str) -> Mapping[str, Any]:
        try:
            response = self._client.get(url, headers=self._headers, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OfficeEnrichmentError(f"NWS {resource_name} lookup failed") from error
        if not isinstance(payload, Mapping):
            raise OfficeEnrichmentError(f"NWS {resource_name} response was not an object")
        return payload


class OfficeWeatherStoryRetriever:
    """Retrieve and normalize one active office collection for one invocation."""

    def __init__(self, client: NWSCollectionClient) -> None:
        self._client = client

    def retrieve(
        self, registry: OfficeRegistry, office_id: str, *, processing_deadline: float
    ) -> NormalizedCollection:
        office = next(
            (record for record in registry.offices if record.office_id == office_id), None
        )
        if office is None or not office.active:
            raise CollectionValidationError("invocation office must be an active registry office")
        response = self._client.fetch(
            str(office.weather_stories_url), processing_deadline=processing_deadline
        )
        return normalize_collection(response, office_id)


def normalize_collection(response: httpx.Response, office_id: str) -> NormalizedCollection:
    """Validate the complete envelope before independently quarantining malformed items."""
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        raise CollectionValidationError("collection response was not JSON-compatible")
    try:
        payload = response.json()
    except ValueError as error:
        raise CollectionValidationError("collection response was not valid JSON") from error
    if not isinstance(payload, Mapping):
        raise CollectionValidationError("collection response was not an object")
    try:
        envelope = NWSWeatherStoryCollectionResponse.model_validate(payload)
    except ValidationError as error:
        raise CollectionValidationError(
            "collection response failed source-contract validation"
        ) from error

    stories: list[WeatherStory] = []
    quarantined: list[QuarantinedStoryItem] = []
    for index, item in enumerate(envelope.stories):
        try:
            story = WeatherStory.model_validate(item)
            story = _validate_story_download(story)
            if story.office_id != office_id:
                raise ValueError("officeId does not match the invocation office")
        except (ValidationError, ValueError) as error:
            quarantined.append(_quarantine(index, error))
        else:
            stories.append(story)
    return NormalizedCollection(
        office_id=office_id, stories=tuple(stories), quarantined=tuple(quarantined)
    )


def _quarantine(index: int, error: ValidationError | ValueError) -> QuarantinedStoryItem:
    if isinstance(error, ValidationError):
        detail = error.errors(include_url=False)[0]
        location = detail.get("loc", ())
        field = str(location[-1]) if location else "item"
        code = str(detail["type"])
    else:
        field = "item"
        code = "invalid_item"
    return QuarantinedStoryItem(
        array_index=index,
        error_code=code[:64],
        affected_field=field[:64],
        error_summary="Weather Story item failed contract validation",
    )


def _validate_source_model[T: BaseModel](
    model: type[T], payload: Mapping[str, Any], resource_name: str
) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise OfficeEnrichmentError(
            f"NWS {resource_name} response failed source-contract validation"
        ) from error


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
