"""Weather MCP tool for demo agent testing."""

from typing import Literal


async def get_weather(
    city: str,
    units: Literal["celsius", "fahrenheit"] = "celsius",
) -> dict[str, str | float]:
    """Get current weather for a city (mock data).

    Args:
        city: City name
        units: Temperature units

    Returns:
        Weather information

    Example:
        >>> result = await get_weather("London", "celsius")
        >>> result["temperature"]
        22.5
    """
    # Mock weather data
    temp_c = 22.5
    temp = temp_c if units == "celsius" else (temp_c * 9 / 5) + 32

    return {
        "city": city,
        "temperature": temp,
        "units": units,
        "conditions": "Partly cloudy",
        "humidity": 65,
    }
