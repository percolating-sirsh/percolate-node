"""Calculator MCP tool for testing agent tool calling."""

from typing import Literal


async def calculate(
    operation: Literal["add", "subtract", "multiply", "divide"],
    a: float,
    b: float,
) -> dict[str, float | str]:
    """Perform basic arithmetic operations.

    This tool allows agents to perform calculations on two numbers.
    Useful for testing MCP tool integration with Pydantic AI agents.

    Args:
        operation: The arithmetic operation to perform
        a: First number
        b: Second number

    Returns:
        Result of the calculation with operation details

    Raises:
        ValueError: If division by zero is attempted

    Example:
        >>> result = await calculate("multiply", 15, 23)
        >>> result["result"]
        345.0
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
