import datetime as dt
from pathlib import Path

import pytest

from mcp_gismeteo.client import parse_day

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(
    params=["moscow_today.html", "moscow_5day.html"], ids=["today", "day5"]
)
def parsed(request):
    html = (FIXTURES / request.param).read_text()
    return parse_day(html, "Europe/Moscow")


def test_eight_three_hour_slots(parsed):
    slots = parsed["slots"]
    assert len(slots) == 8
    times = [dt.datetime.fromisoformat(s["time"]) for s in slots]
    for a, b in zip(times, times[1:]):
        assert (b - a) == dt.timedelta(hours=3)
    assert times[0].hour == 0
    assert times[-1].hour == 21


def test_slot_fields(parsed):
    for slot in parsed["slots"]:
        assert isinstance(slot["temp_c"], int)
        assert isinstance(slot["precip_mm"], float)
        wind = slot["wind"]
        assert isinstance(wind["speed_ms"], int)
        assert isinstance(wind["gust_ms"], int)
        if wind["direction"] is not None:
            assert wind["direction_deg"] in range(0, 360)


def test_sunrise_before_sunset(parsed):
    sunrise = dt.datetime.fromisoformat(parsed["sunrise"])
    sunset = dt.datetime.fromisoformat(parsed["sunset"])
    assert sunrise < sunset


def test_dates_match_page_day():
    html = (FIXTURES / "moscow_5day.html").read_text()
    parsed = parse_day(html, "Europe/Moscow")
    assert parsed["sunrise"].startswith("2026-11-15")
    assert parsed["slots"][0]["time"].startswith("2026-11-15")
