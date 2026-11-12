from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.gismeteo.ru"
SEARCH_URL = f"{BASE_URL}/mq/city/q/"
LATLNG_URL = f"{BASE_URL}/mq/city/lat-lng/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

MAX_FORECAST_DAYS = 10

WIND_DEGREES = {
    "С": 0, "СВ": 45, "В": 90, "ЮВ": 135,
    "Ю": 180, "ЮЗ": 225, "З": 270, "СЗ": 315,
}


class GismeteoError(Exception):
    pass


class CityNotFound(GismeteoError):
    pass


class DateOutOfRange(GismeteoError):
    pass


class FetchError(GismeteoError):
    pass


@dataclass
class City:
    id: int
    slug: str
    name: str
    country_code: str | None
    timezone: str


def _make_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html",
            "Accept-Language": "ru",
        },
        timeout=15,
        follow_redirects=True,
    )


def _city_from_payload(item: dict) -> City:
    name = (
        item.get("translations", {})
        .get("ru", {})
        .get("city", {})
        .get("name")
        or item.get("slug", "")
    )
    return City(
        id=item["id"],
        slug=item["slug"],
        name=name,
        country_code=(item.get("country") or {}).get("code"),
        timezone=item.get("timeZoneName") or "UTC",
    )


def _pick_city(items: list[dict], name: str) -> dict:
    norm = name.strip().lower()
    for item in items:
        ru_name = (
            item.get("translations", {})
            .get("ru", {})
            .get("city", {})
            .get("name", "")
        )
        if ru_name.lower() == norm or item.get("slug", "").lower() == norm:
            return item
    return items[0]


def search_city(name: str, client: httpx.Client | None = None) -> City:
    client = client or _make_client()
    resp = client.get(
        SEARCH_URL,
        params={
            "q": name,
            "geo": "ru",
            "latitude": "0",
            "longitude": "0",
            "limit": "10",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("data") or []
    if not payload.get("meta", {}).get("status") or not items:
        raise CityNotFound(f"Город не найден: {name!r}")
    return _city_from_payload(_pick_city(items, name))


def resolve_city(
    latitude: float, longitude: float, client: httpx.Client | None = None
) -> City:
    client = client or _make_client()
    resp = client.get(
        LATLNG_URL,
        params={"latitude": str(latitude), "longitude": str(longitude), "geo": "ru"},
    )
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("data") or []
    if not payload.get("meta", {}).get("status") or not items:
        raise CityNotFound(
            f"Рядом с координатами ({latitude}, {longitude}) пункт не найден"
        )
    first = items[0] if isinstance(items, list) else items
    return _city_from_payload(first)


def day_path(offset: int) -> str:
    if offset == 0:
        return "/"
    if offset == 1:
        return "/tomorrow/"
    return f"/{offset + 1}-day/"


def _day_offset(city: City, target_date: dt.date) -> int:
    today = dt.datetime.now(ZoneInfo(city.timezone)).date()
    offset = (target_date - today).days
    if not 0 <= offset < MAX_FORECAST_DAYS:
        raise DateOutOfRange(
            f"Дата {target_date} вне диапазона: прогноз доступен с {today} "
            f"по {today + dt.timedelta(days=MAX_FORECAST_DAYS - 1)} "
            f"(время города {city.name})"
        )
    return offset


def fetch_day_page(
    city: City, target_date: dt.date, client: httpx.Client | None = None
) -> tuple[str, str]:
    client = client or _make_client()
    url = f"{BASE_URL}/weather-{city.slug}-{city.id}{day_path(_day_offset(city, target_date))}"
    resp = client.get(url)
    if resp.status_code != 200:
        raise FetchError(f"gismeteo.ru вернул HTTP {resp.status_code} для {url}")
    if "widget-weather-parameters" not in resp.text:
        raise FetchError(
            "Страница не содержит прогноз (возможна блокировка WAF или изменение вёрстки)"
        )
    return resp.text, url


def _text(tag) -> str | None:
    t = tag.get_text(strip=True) if tag else None
    return t or None


def _float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text.replace(",", ".").replace("−", "-"))
    except ValueError:
        return None


def _int(text: str | None) -> int | None:
    v = _float(text)
    return int(v) if v is not None else None


def _local_iso(ts: int, tz: ZoneInfo) -> str:
    return dt.datetime.fromtimestamp(int(ts), tz).isoformat()


def parse_day(html: str, timezone: str) -> dict:
    tz = ZoneInfo(timezone)
    soup = BeautifulSoup(html, "lxml")
    widget = soup.select_one(".widget-weather-parameters")
    if widget is None:
        raise FetchError("Виджет прогноза не найден на странице")

    time_items = widget.select(
        ".widget-row-datetime-time .row-item time-value[timestamp]"
    )
    times = [_local_iso(tv["timestamp"], tz) for tv in time_items]
    n = len(times)

    def _column(rows: list, i: int):
        return rows[i] if i < len(rows) else None

    icon_items = widget.select(".widget-row-icon .row-item")
    temp_row = widget.select_one('.widget-row-chart-temperature-air, [data-row="temperature-air"]')
    temp_vals = (
        [tv.get("value") for tv in temp_row.select("temperature-value[value]")]
        if temp_row
        else []
    )
    precip_row = widget.select_one('[data-row="precipitation-bars"]')
    precip_items = precip_row.select(".row-item") if precip_row else []
    wind_row = widget.select_one('[data-row="wind"]')
    wind_items = wind_row.select(".row-item") if wind_row else []

    slots = []
    for i in range(n):
        icon = _column(icon_items, i)
        wind = _column(wind_items, i)
        direction = None
        speed = gust = None
        if wind:
            dir_tag = wind.select_one(".wind-direction")
            direction = _text(dir_tag)
            sp = wind.select_one(".wind-speed speed-value[value]")
            speed = _int(sp.get("value") if sp else None)
            gu = wind.select_one(".wind-gust speed-value[value]")
            gust = _int(gu.get("value") if gu else None)
        precip = _column(precip_items, i)
        precip_mm = None
        if precip:
            unit = precip.select_one(".item-unit")
            if unit and unit.get("value") is not None:
                precip_mm = _float(unit["value"])
            else:
                precip_mm = _float(_text(unit) or _text(precip))
        slots.append(
            {
                "time": times[i],
                "description": icon.get("data-tooltip") if icon else None,
                "temp_c": _int(_column(temp_vals, i)),
                "precip_mm": precip_mm,
                "wind": {
                    "direction": direction,
                    "direction_deg": WIND_DEGREES.get(direction or ""),
                    "speed_ms": speed,
                    "gust_ms": gust,
                },
            }
        )

    sunrise = sunset = None
    astro = soup.select_one(".widget-astro .astro-sun")
    if astro:
        sun_times = astro.select("time-value[timestamp]")
        if len(sun_times) >= 2:
            sunrise = _local_iso(sun_times[0]["timestamp"], tz)
            sunset = _local_iso(sun_times[1]["timestamp"], tz)

    return {"sunrise": sunrise, "sunset": sunset, "slots": slots}


def get_weather(
    city_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    date: str | None = None,
    client: httpx.Client | None = None,
) -> dict:
    if (latitude is None) != (longitude is None):
        raise GismeteoError("Задайте обе координаты: latitude и longitude")
    if latitude is None and not (city_name and city_name.strip()):
        raise GismeteoError("Укажите город (city) или координаты (latitude + longitude)")

    target_date = None
    if date:
        try:
            target_date = dt.date.fromisoformat(date)
        except ValueError:
            raise GismeteoError(f"Некорректная дата {date!r}: ожидается YYYY-MM-DD")

    client = client or _make_client()
    if latitude is not None:
        city = resolve_city(latitude, longitude, client)
    else:
        city = search_city(city_name.strip(), client)

    if target_date is None:
        target_date = dt.datetime.now(ZoneInfo(city.timezone)).date()

    html, url = fetch_day_page(city, target_date, client)
    parsed = parse_day(html, city.timezone)
    return {
        "city": {
            "id": city.id,
            "slug": city.slug,
            "name": city.name,
            "country": city.country_code,
            "timezone": city.timezone,
        },
        "date": target_date.isoformat(),
        "source_url": url,
        **parsed,
    }
