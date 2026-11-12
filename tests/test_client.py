import json
from pathlib import Path

import httpx
import pytest

from mcp_gismeteo.client import (
    CityNotFound,
    GismeteoError,
    day_path,
    get_weather,
    resolve_city,
    search_city,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_client(body: str, status: int = 200, content_type: str = "application/json"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status, text=body, headers={"Content-Type": content_type}
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_day_path():
    assert day_path(0) == "/"
    assert day_path(1) == "/tomorrow/"
    assert day_path(2) == "/3-day/"
    assert day_path(9) == "/10-day/"


def test_search_city_picks_exact_match():
    body = (FIXTURES / "search_moscow.json").read_text()
    city = search_city("москва", client=_mock_client(body))
    assert city.id == 4368
    assert city.slug == "moscow"
    assert city.name == "Москва"
    assert city.timezone == "Europe/Moscow"


def test_search_city_not_found():
    body = '{"meta":{"status":true},"data":[]}'
    with pytest.raises(CityNotFound):
        search_city("zzz", client=_mock_client(body))


def test_resolve_city_returns_nearest():
    body = (FIXTURES / "latlng_spb.json").read_text()
    city = resolve_city(59.94, 30.31, client=_mock_client(body))
    assert city.id == 4079
    assert city.slug == "sankt-peterburg"


def test_resolve_city_empty_result():
    body = '{"meta":{"status":true},"data":[]}'
    with pytest.raises(CityNotFound):
        resolve_city(0.0, 0.0, client=_mock_client(body))


def test_get_weather_requires_city_or_coords():
    with pytest.raises(GismeteoError):
        get_weather()
    with pytest.raises(GismeteoError):
        get_weather(latitude=55.0)  # longitude missing
    with pytest.raises(GismeteoError):
        get_weather(city_name="москва", date="15 ноября")


@pytest.mark.live
def test_live_moscow_today():
    result = get_weather(city_name="москва")
    assert result["city"]["id"] == 4368
    assert len(result["slots"]) == 8
    assert result["sunrise"] < result["sunset"]


@pytest.mark.live
def test_live_coordinates():
    result = get_weather(latitude=59.94, longitude=30.31)
    assert result["city"]["slug"] == "sankt-peterburg"
