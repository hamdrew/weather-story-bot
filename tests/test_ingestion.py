from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import httpx
import pytest

from weather_story_bot.config import EnvironmentConfig, NWSOfficeSeedSet, OfficeCoordinates
from weather_story_bot.ingestion import (
    CollectionValidationError,
    NWSOfficeResponse,
    NWSRegionalOfficeResponse,
    NWSWeatherStoryCollectionResponse,
    OfficeEnrichmentError,
    OfficeRegistrySeeder,
    OfficeWeatherStoryRetriever,
    normalize_collection,
)
from weather_story_bot.nws_client import NWS_ACCEPT, NWS_USER_AGENT, NWSCollectionClient

FIXTURES = Path(__file__).parent / "fixtures" / "nws"


def load_fixture(name: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def environment() -> EnvironmentConfig:
    return EnvironmentConfig(
        schema_version=1,
        environment="dev",
        telegram_mode="mock",
        nws_image_host_allowlist=("weather.gov", "*.weather.gov"),
        active_office_ids=("MKX",),
        office_channels={"MKX": "mock:mkx"},
        alert_recipient="mock:operator",
    )


class FixedGeocoder:
    def geocode(self, address: object) -> OfficeCoordinates:
        del address
        return OfficeCoordinates(latitude=43.04, longitude=-88.46)


def test_registry_seeder_enriches_every_seed_and_only_activates_configured_office() -> None:
    user_agents: list[str] = []
    responses = {
        "https://api.weather.gov/offices/MKX": load_fixture("office_mkx.v1.json"),
        "https://api.weather.gov/offices/CRH": load_fixture("regional_office_crh.v1.json"),
        "https://api.weather.gov/offices/GRB": {
            "id": "GRB",
            "name": "Green Bay, WI",
            "address": {
                "streetAddress": "2485 South Point Road",
                "addressLocality": "Green Bay",
                "addressRegion": "WI",
                "postalCode": "54313",
            },
            "sameAs": "https://www.weather.gov/grb/",
            "nwsRegion": "cr",
            "parentOrganization": "https://api.weather.gov/offices/CRH",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        user_agents.append(request.headers["User-Agent"])
        return httpx.Response(200, json=responses[str(request.url)])

    registry = OfficeRegistrySeeder(
        httpx.Client(transport=httpx.MockTransport(handler)), FixedGeocoder()
    ).seed(
        NWSOfficeSeedSet.model_validate(
            {"schema_version": 1, "source": "https://example.test", "office_ids": ("MKX", "GRB")}
        ),
        environment(),
    )

    assert [office.office_id for office in registry.offices] == ["MKX", "GRB"]
    assert registry.offices[0].active is True
    assert registry.offices[0].timezone == "America/Chicago"
    assert registry.offices[1].active is False
    assert registry.offices[1].telegram_channel_id is None
    assert user_agents == [NWS_USER_AGENT, NWS_USER_AGENT, NWS_USER_AGENT, NWS_USER_AGENT]


def test_versioned_flat_json_ld_office_and_regional_office_fixtures_match_source_models() -> None:
    office = NWSOfficeResponse.model_validate(load_fixture("office_mkx.v1.json"))
    region = NWSRegionalOfficeResponse.model_validate(load_fixture("regional_office_crh.v1.json"))

    assert office.office_id == "MKX"
    assert str(office.parent_organization) == "https://api.weather.gov/offices/CRH"
    assert office.address.locality == "Dousman"
    assert region.office_id == "CRH"


def test_office_source_model_rejects_missing_or_non_https_contract_fields() -> None:
    fixture = load_fixture("office_mkx.v1.json")

    with pytest.raises(ValueError):
        NWSOfficeResponse.model_validate(fixture | {"sameAs": "http://www.weather.gov/mkx"})
    with pytest.raises(ValueError):
        NWSOfficeResponse.model_validate(
            {key: value for key, value in fixture.items() if key != "nwsRegion"}
        )
    with pytest.raises(ValueError, match="NWS office resource"):
        NWSOfficeResponse.model_validate(
            fixture | {"parentOrganization": "https://untrusted.example/offices/CRH"}
        )


@pytest.mark.parametrize(
    "parent_organization",
    [
        "https://attacker@api.weather.gov/offices/CRH",
        "https://api.weather.gov:443/offices/CRH",
        "https://api.weather.gov/offices/CRH?redirect=https://attacker.example",
        "https://api.weather.gov/offices/CRH#redirect",
        "https://api.weather.gov/offices/crh",
        "https://api.weather.gov/regions/CRH",
    ],
)
def test_office_source_model_rejects_parent_organization_ssrf_bypasses(
    parent_organization: str,
) -> None:
    with pytest.raises(ValueError, match="NWS office resource"):
        NWSOfficeResponse.model_validate(
            load_fixture("office_mkx.v1.json") | {"parentOrganization": parent_organization}
        )


@pytest.mark.parametrize(
    "office_payload, region_payload",
    [
        ({}, None),
        ([], None),
        (load_fixture("office_mkx.v1.json") | {"id": "GRB"}, None),
        (load_fixture("office_mkx.v1.json"), {}),
        (load_fixture("office_mkx.v1.json"), []),
    ],
)
def test_registry_seeder_translates_malformed_office_and_region_payloads(
    office_payload: object, region_payload: object | None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = office_payload if request.url.path.endswith("/MKX") else region_payload
        return httpx.Response(200, json=payload)

    seeder = OfficeRegistrySeeder(
        httpx.Client(transport=httpx.MockTransport(handler)), FixedGeocoder()
    )

    with pytest.raises(OfficeEnrichmentError):
        seeder.seed(
            NWSOfficeSeedSet.model_validate(
                {"schema_version": 1, "source": "https://example.test", "office_ids": ("MKX",)}
            ),
            environment(),
        )


@pytest.mark.parametrize("failure", ["http", "invalid_json", "non_object"])
def test_registry_seeder_translates_http_and_json_failures(failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "http":
            return httpx.Response(500, request=request)
        if failure == "invalid_json":
            return httpx.Response(200, content=b"not json")
        return httpx.Response(200, json=[])

    seeder = OfficeRegistrySeeder(
        httpx.Client(transport=httpx.MockTransport(handler)), FixedGeocoder()
    )

    with pytest.raises(OfficeEnrichmentError, match="NWS office"):
        seeder.seed(
            NWSOfficeSeedSet.model_validate(
                {"schema_version": 1, "source": "https://example.test", "office_ids": ("MKX",)}
            ),
            environment(),
        )


def test_registry_seeder_enforces_required_headers_after_caller_overrides() -> None:
    observed_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_headers.append(request.headers)
        payload = (
            load_fixture("office_mkx.v1.json")
            if request.url.path.endswith("/MKX")
            else load_fixture("regional_office_crh.v1.json")
        )
        return httpx.Response(200, json=payload)

    OfficeRegistrySeeder(
        httpx.Client(transport=httpx.MockTransport(handler)),
        FixedGeocoder(),
        headers={"Accept": "text/plain", "User-Agent": "unidentified-client"},
    ).seed(
        NWSOfficeSeedSet.model_validate(
            {"schema_version": 1, "source": "https://example.test", "office_ids": ("MKX",)}
        ),
        environment(),
    )

    assert all(headers["Accept"] == NWS_ACCEPT for headers in observed_headers)
    assert all(headers["User-Agent"] == NWS_USER_AGENT for headers in observed_headers)


def story(**overrides: object) -> dict[str, object]:
    return {
        "officeId": "MKX",
        "startTime": "2026-08-15T12:00:00+00:00",
        "endTime": "2026-08-15T18:00:00+00:00",
        "updateTime": "2026-08-15T12:05:00+00:00",
        "title": "Heat advisory",
        "description": "Dangerous heat this afternoon.",
        "altText": "Heat index map",
        "priority": True,
        "order": 1,
        "download": "https://www.weather.gov/images/mkx/123e4567-e89b-12d3-a456-426614174000",
    } | overrides


def response(payload: object, *, content_type: str = "application/ld+json") -> httpx.Response:
    return httpx.Response(200, json=payload, headers={"content-type": content_type})


def test_normalization_uses_office_and_download_uuid_only_after_validating_each_item() -> None:
    collection = normalize_collection(
        response({"stories": [story(), story(download="https://weather.gov/not-a-uuid")]}), "MKX"
    )

    assert collection.stories[0].canonical_identity == (
        "MKX",
        "123e4567-e89b-12d3-a456-426614174000",
    )
    assert collection.quarantined[0].array_index == 1
    assert (
        collection.quarantined[0].error_summary == "Weather Story item failed contract validation"
    )


def test_versioned_weather_story_contract_fixtures_normalize() -> None:
    success = normalize_collection(
        response(load_fixture("weatherstories_mkx_success.v1.json")), "MKX"
    )
    empty = normalize_collection(response(load_fixture("weatherstories_mkx_empty.v1.json")), "MKX")

    assert len(success.stories) == 1
    assert success.quarantined == ()
    assert empty.stories == ()


def test_versioned_weather_story_fixture_matches_collection_source_model() -> None:
    source = NWSWeatherStoryCollectionResponse.model_validate(
        load_fixture("weatherstories_mkx_success.v1.json")
    )

    assert len(source.stories) == 1


@pytest.mark.parametrize("field", ["startTime", "endTime", "updateTime"])
@pytest.mark.parametrize("value", ["2026-08-15", 1_755_249_600])
def test_normalization_quarantines_non_datetime_timestamp_values(field: str, value: object) -> None:
    collection = normalize_collection(response({"stories": [story(**{field: value})]}), "MKX")

    assert collection.stories == ()
    assert collection.quarantined[0].array_index == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"startTime": "not-a-timestamp"},
        {"download": "http://www.weather.gov/images/mkx/123e4567-e89b-12d3-a456-426614174000"},
        {"officeId": "GRB"},
    ],
)
def test_normalization_quarantines_adjacent_item_contract_failures(
    overrides: dict[str, object],
) -> None:
    collection = normalize_collection(response({"stories": [story(**overrides)]}), "MKX")

    assert collection.stories == ()
    assert collection.quarantined[0].array_index == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"stories": {}},
        {"stories": [], "next": "https://api.weather.gov/page/2"},
    ],
)
def test_normalization_rejects_invalid_or_incomplete_collection_envelopes(payload: object) -> None:
    with pytest.raises(CollectionValidationError):
        normalize_collection(response(payload), "MKX")


@pytest.mark.parametrize(
    "raw_response, message",
    [
        (httpx.Response(200, json={"stories": []}, headers={"content-type": "text/plain"}), "JSON"),
        (
            httpx.Response(200, content=b"not json", headers={"content-type": "application/json"}),
            "valid JSON",
        ),
        (httpx.Response(200, json=[], headers={"content-type": "application/json"}), "object"),
    ],
)
def test_normalization_rejects_non_json_invalid_json_and_non_object_bodies(
    raw_response: httpx.Response, message: str
) -> None:
    with pytest.raises(CollectionValidationError, match=message):
        normalize_collection(raw_response, "MKX")


def test_retriever_only_requests_the_active_invocation_office() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"stories": []}, headers={"content-type": "application/json"}
        )

    registry = OfficeRegistrySeeder(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "id": "MKX",
                        "name": "Milwaukee/Sullivan, WI",
                        "address": {
                            "streetAddress": "N3533 Hardscrabble Road",
                            "addressLocality": "Dousman",
                            "addressRegion": "WI",
                            "postalCode": "53118",
                        },
                        "sameAs": "https://www.weather.gov/mkx/",
                        "nwsRegion": "cr",
                        "parentOrganization": "https://api.weather.gov/offices/CRH",
                    }
                    if str(request.url).endswith("/MKX")
                    else {"id": "CRH", "name": "Central", "sameAs": "https://www.weather.gov/crh/"},
                )
            )
        ),
        FixedGeocoder(),
    ).seed(
        NWSOfficeSeedSet.model_validate(
            {"schema_version": 1, "source": "https://example.test", "office_ids": ("MKX",)}
        ),
        environment(),
    )

    result = OfficeWeatherStoryRetriever(
        NWSCollectionClient(httpx.Client(transport=httpx.MockTransport(handler)), clock=lambda: 0)
    ).retrieve(registry, "MKX", processing_deadline=100)

    assert result.office_id == "MKX"
    assert result.stories == ()


@pytest.mark.parametrize("office_id", ["GRB", "UNKNOWN"])
def test_retriever_rejects_unknown_or_inactive_invocation_office(office_id: str) -> None:
    registry = OfficeRegistrySeeder(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "id": "MKX",
                        "name": "Milwaukee/Sullivan, WI",
                        "address": {
                            "streetAddress": "N3533 Hardscrabble Road",
                            "addressLocality": "Dousman",
                            "addressRegion": "WI",
                            "postalCode": "53118",
                        },
                        "sameAs": "https://www.weather.gov/mkx/",
                        "nwsRegion": "cr",
                        "parentOrganization": "https://api.weather.gov/offices/CRH",
                    }
                    if request.url.path.endswith("/MKX")
                    else (
                        {
                            "id": "GRB",
                            "name": "Green Bay, WI",
                            "address": {
                                "streetAddress": "2485 South Point Road",
                                "addressLocality": "Green Bay",
                                "addressRegion": "WI",
                                "postalCode": "54313",
                            },
                            "sameAs": "https://www.weather.gov/grb/",
                            "nwsRegion": "cr",
                            "parentOrganization": "https://api.weather.gov/offices/CRH",
                        }
                        if request.url.path.endswith("/GRB")
                        else {
                            "id": "CRH",
                            "name": "Central",
                            "sameAs": "https://www.weather.gov/crh/",
                        }
                    ),
                )
            )
        ),
        FixedGeocoder(),
    ).seed(
        NWSOfficeSeedSet.model_validate(
            {
                "schema_version": 1,
                "source": "https://example.test",
                "office_ids": ("MKX", "GRB"),
            }
        ),
        environment(),
    )
    retriever = OfficeWeatherStoryRetriever(
        NWSCollectionClient(
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: pytest.fail(f"unexpected request to {request.url}")
                )
            ),
            clock=lambda: 0,
        )
    )

    with pytest.raises(CollectionValidationError, match="active registry office"):
        retriever.retrieve(registry, office_id, processing_deadline=100)
