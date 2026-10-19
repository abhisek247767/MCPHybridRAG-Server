import ast
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcphybridrag_server import invoice_tools, rag
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
    extra_details: dict[str, Any] | None = None,
) -> dict:
    """Save an invoice (client, amount, dates, late fee terms) to the database.

    Args:
        client_name: Who the invoice is billed to.
        total_amount: Final amount due, as a number without currency symbol.
        due_date: Payment due date, copied exactly as printed on the invoice.
        invoice_number: Invoice number/ID printed on the invoice.
        issue_date: Invoice date, copied exactly as printed on the invoice.
        currency: Currency code, e.g. USD or INR.
        late_fee_terms: Late payment fee terms, as written on the invoice.
        extra_details: Any OTHER fields printed on this invoice that don't fit
            above, as {"field_name": value}. Examples: po_number, line_items
            (list of {description, quantity, unit_price, amount}), subtotal,
            tax_rate, tax_amount, bill_to_address, ship_to, payable_to,
            payment_terms, payment_method, notes. Only data shown on the
            invoice itself; never add anything that is not on the invoice.
    """
    return invoice_tools.save_invoice(
        client_name=client_name,
        total_amount=total_amount,
        due_date=due_date,
        invoice_number=invoice_number,
        issue_date=issue_date,
        currency=currency,
        late_fee_terms=late_fee_terms,
        extra_details=extra_details,
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
def get_invoice(invoice_number: str) -> dict:
    """Look up one saved invoice by its invoice number.

    Args:
        invoice_number: The invoice number/ID, e.g. INV-102.
    """
    return invoice_tools.get_invoice(invoice_number)


@mcp.tool()
def list_overdue_invoices() -> dict:
    """List saved invoices whose due date has already passed (overdue, late payments)."""
    return invoice_tools.list_overdue_invoices()


@mcp.tool()
def invoices_due_between(start_date: str, end_date: str) -> dict:
    """List saved invoices due within a period: this week, this month, or between two dates.

    Args:
        start_date: First day of the range, YYYY-MM-DD.
        end_date: Last day of the range, YYYY-MM-DD.
    """
    return invoice_tools.invoices_due_between(start_date, end_date)


@mcp.tool()
def total_due_by_client(client_name: str) -> dict:
    """Add up how much one client owes in total across their saved invoices.

    Args:
        client_name: The client's name, or part of it.
    """
    return invoice_tools.total_due_by_client(client_name)


@mcp.tool()
def days_overdue(due_date: str) -> dict:
    """Calculate how many days a payment is overdue, compared with today's date.

    Args:
        due_date: The due date in YYYY-MM-DD format.
    """
    return invoice_tools.days_overdue(due_date)


@mcp.tool()
def search_documents(query: str) -> str:
    """Search indexed documents for information relevant to a question.

    Args:
        query: What to look for, in plain words.
    """
    if not query.strip():
        raise ValueError("query cannot be empty.")

    results = rag.search(query)

    if not results:
        return (
            "No relevant documents were found. "
            "If none have been indexed yet, run: uv run mcphybridrag-ingest"
        )

    return "\n\n".join(
        f"Source: {doc.metadata.get('source', 'unknown')}\n"
        f"Content: {doc.page_content}"
        for doc in results
    )