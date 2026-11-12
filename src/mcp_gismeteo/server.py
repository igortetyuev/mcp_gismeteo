from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import GismeteoError, get_weather

mcp = MCPServer("gismeteo")


@mcp.tool()
def get_current_weather(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    date: str | None = None,
) -> dict:
    """Weather forecast for a city from gismeteo.ru (data is in Russian).

    Provide either a city name (city) or coordinates (latitude + longitude);
    coordinates take precedence when both are given. date is an optional
    ISO date (YYYY-MM-DD); today is used when omitted. Forecasts are
    available up to 10 days ahead. Returns hourly-resolution slots (3-hour
    step) with temperature, precipitation, wind and sunrise/sunset.
    """
    try:
        return get_weather(
            city_name=city, latitude=latitude, longitude=longitude, date=date
        )
    except GismeteoError as e:
        raise ToolError(str(e))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
