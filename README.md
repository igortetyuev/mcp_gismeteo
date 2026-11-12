# mcp-gismeteo

MCP-сервер, который парсит gismeteo.ru и отдаёт прогноз погоды на день
без ключей и API-регистрации.

## Инструмент

### `get_current_weather`

| Аргумент | Тип | Описание |
|---|---|---|
| `city` | `str?` | Название города («москва», «berlin»). Искать по имени. |
| `latitude` | `float?` | Широта — альтернатива `city`, ищется ближайший пункт. |
| `longitude` | `float?` | Долгота — задаётся вместе с `latitude`. |
| `date` | `str?` | ISO `YYYY-MM-DD`. По умолчанию — сегодня (время города). |

- Нужен `city` **или** пара `latitude`+`longitude`; при задании обоих — координаты в приоритете.
- Горизонт прогноза — 10 дней вперёд включительно.
- В ответе всегда возвращается найденный `city` — видно, какой пункт подставился.

### Ответ

```json
{
  "city": {"id": 4368, "slug": "moscow", "name": "Москва", "country": "RU", "timezone": "Europe/Moscow"},
  "date": "2026-11-11",
  "source_url": "https://www.gismeteo.ru/weather-moscow-4368/",
  "sunrise": "2026-11-11T07:56:20+03:00",
  "sunset": "2026-11-11T16:30:01+03:00",
  "slots": [
    {
      "time": "2026-11-11T00:00:00+03:00",
      "description": "пасмурно, небольшой снег с дождём",
      "temp_c": 4,
      "precip_mm": 0.05,
      "wind": {"direction": "Ю", "direction_deg": 180, "speed_ms": 1, "gust_ms": 4}
    }
  ]
}
```

`slots` — 8 колонок с шагом 3 часа на локальные сутки города (00:00–21:00)
— это максимальная детализация, которую gismeteo.ru отдаёт на странице дня.
Описания — по-русски, как на сайте.

## Установка и запуск

```bash
uv sync
uv run mcp-gismeteo        # stdio-сервер
```

### Подключение из MCP-клиента (stdio)

```json
{
  "mcpServers": {
    "gismeteo": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp_gismeteo", "mcp-gismeteo"]
    }
  }
}
```

## Как это работает

1. Поиск: `GET /mq/city/q/?q=…&geo=ru&latitude=0&longitude=0&limit=10` или
   `GET /mq/city/lat-lng/?latitude=…&longitude=…&geo=ru` → `id`, `slug`, таймзона.
2. Страница дня: `/weather-{slug}-{id}/` (сегодня), `/tomorrow/`, `/3-day/` … `/10-day/`.
3. Парсинг HTML-виджета `widget-weather-parameters` (строки времени, иконки,
   температуры, осадки, ветра) + `widget-astro` (восход/закат).

## Тесты

```bash
uv run pytest            # офлайн, по сохранённым фикстурам
uv run pytest -m live    # + живые запросы к gismeteo.ru
```

## Ограничения

- Только будущие даты: сегодня + 9 дней.
- Шаг данных — 3 часа (почасовой детализации на страницах дня нет).
- Парсинг зависит от вёрстки gismeteo.ru; при её смене упадут тесты на фикстурах.
- Перед сайтом стоит WAF — запросы идут с браузерным User-Agent; при блокировке
  инструмент вернёт понятную ошибку.
