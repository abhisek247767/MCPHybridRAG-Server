import ast
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from mcphybridrag_server.server import evaluate

mcp = FastMCP("Calculator and Date Server", host="127.0.0.1", port=8000)

@mcp.tool()
def calculate(expression: str) -> str:
    """Calculate a basic arithmetic expression.

    Supports addition, subtraction, multiplication, division,
    floor division, modulo, powers, and parentheses.

    Example: (125 * 48) + 10
    """
    if not expression.strip():
        raise ValueError("Expression cannot be empty.")

    if len(expression) > 200:
        raise ValueError("Expression is too long.")

    try:
        tree = ast.parse(expression, mode="eval")
        result = evaluate(tree)
        return str(result)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"Could not calculate expression: {exc}") from exc


@mcp.tool()
def get_current_date() -> str:
    """Get the current local date, time, and timezone."""
    return datetime.now().astimezone().isoformat()


