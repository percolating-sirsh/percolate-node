"""Demo MCP server with tools and resources for testing agent-let framework.

This server provides:
- Tools: calculator, get_weather
- Resources: demo://info, demo://config
"""

from typing import Literal

from fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Demo MCP Server")


# --- Tools ---


@mcp.tool()
async def calculator(
    operation: Literal["add", "subtract", "multiply", "divide"],
    a: float,
    b: float,
) -> dict[str, float | str]:
    """Perform basic arithmetic operations.

    This tool allows agents to perform calculations on two numbers.

    Args:
        operation: The arithmetic operation to perform
        a: First number
        b: Second number

    Returns:
        Result of the calculation with operation details
    """
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")

    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
    }


@mcp.tool()
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


# --- Resources ---


@mcp.resource("demo://info")
async def get_demo_info() -> str:
    """Get information about this demo MCP server."""
    return """# Demo MCP Server

This is a demonstration MCP server for testing the agent-let framework.

## Available Tools

1. **calculator**: Perform arithmetic operations (add, subtract, multiply, divide)
2. **get_weather**: Get mock weather data for a city

## Available Resources

1. **demo://info**: This information document
2. **demo://config**: Server configuration

## Usage

Tools can be called by agents that reference this MCP server in their schema.
Resources provide static or dynamic information accessible via URI.
"""


@mcp.resource("demo://config")
async def get_demo_config() -> str:
    """Get server configuration."""
    return """# Demo MCP Server Configuration

- Server Name: Demo MCP Server
- Version: 1.0.0
- Tools: 2
- Resources: 2
- Features:
  - Basic arithmetic operations
  - Mock weather data
  - Configuration and info resources
"""


if __name__ == "__main__":
    # Run server in stdio mode for MCP protocol
    mcp.run()
