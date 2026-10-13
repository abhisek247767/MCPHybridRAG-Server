import ast
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from mcphybridrag_server import invoice_tools
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

@mcp.tool()
def save_invoice(
    client_name: str,
    total_amount: float,
    due_date: str | None = None,
    invoice_number: str | None = None,
    issue_date: str | None = None,
    currency: str | None = None,
    late_fee_terms: str | None = None,
) -> dict:
    """Save an invoice (client, amount, dates, late fee terms) to the database.

    Args:
        client_name: Who the invoice is billed to.
        total_amount: Final amount due, as a number without currency symbol.
        due_date: Payment due date, YYYY-MM-DD.
        invoice_number: Invoice number/ID printed on the invoice.
        issue_date: Invoice date, YYYY-MM-DD.
        currency: Currency code, e.g. USD or INR.
        late_fee_terms: Late payment fee terms, as written on the invoice.
    """
    return invoice_tools.save_invoice(
        client_name=client_name,
        total_amount=total_amount,
        due_date=due_date,
        invoice_number=invoice_number,
        issue_date=issue_date,
        currency=currency,
        late_fee_terms=late_fee_terms,
    )


@mcp.tool()
def list_invoices(client_name: str | None = None, limit: int = 20) -> list[dict]:
    """List saved invoices from the database, optionally filtered by client name.

    Args:
        client_name: Part of the client name to search for; empty lists all.
        limit: Maximum number of invoices to return (1-100).
    """
    return invoice_tools.list_invoices(client_name=client_name, limit=limit)


@mcp.tool()
def days_overdue(due_date: str) -> dict:
    """Calculate how many days a payment is overdue, compared with today's date.

    Args:
        due_date: The due date in YYYY-MM-DD format.
    """
    return invoice_tools.days_overdue(due_date)
