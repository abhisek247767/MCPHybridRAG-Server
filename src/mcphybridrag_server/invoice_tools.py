"""Invoice storage in SQLite, plus overdue-date helpers."""

import os
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

# Database file. Defaults to invoices.db in the server project folder.
DB_PATH = Path(
    os.getenv("INVOICE_DB_PATH", Path(__file__).resolve().parents[2] / "invoices.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name    TEXT    NOT NULL,
    invoice_number TEXT    UNIQUE,
    issue_date     TEXT,
    due_date       TEXT,
    total_amount   REAL    NOT NULL,
    currency       TEXT,
    late_fee_terms TEXT,
    created_at     TEXT    NOT NULL
)
"""


def connect() -> sqlite3.Connection:
    """Open the database and make sure the table exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute(SCHEMA)
    return conn


def parse_date(value: str | None, field: str) -> str | None:
    """Check a date is YYYY-MM-DD; empty means not provided."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD, got {value!r}") from exc


def save_invoice(
    client_name: str,
    total_amount: float,
    due_date: str | None = None,
    invoice_number: str | None = None,
    issue_date: str | None = None,
    currency: str | None = None,
    late_fee_terms: str | None = None,
) -> dict:
    """Insert one invoice and return the saved row."""
    if not client_name.strip():
        raise ValueError("client_name cannot be empty.")
    if total_amount < 0:
        raise ValueError("total_amount cannot be negative.")

    row = {
        "client_name": client_name.strip(),
        "invoice_number": (invoice_number or "").strip() or None,
        "issue_date": parse_date(issue_date, "issue_date"),
        "due_date": parse_date(due_date, "due_date"),
        "total_amount": float(total_amount),
        "currency": (currency or "").strip().upper() or None,
        "late_fee_terms": (late_fee_terms or "").strip() or None,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    # closing() closes the connection; "with conn" commits (or rolls back).
    with closing(connect()) as conn, conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO invoices (client_name, invoice_number, issue_date,
                    due_date, total_amount, currency, late_fee_terms, created_at)
                VALUES (:client_name, :invoice_number, :issue_date,
                    :due_date, :total_amount, :currency, :late_fee_terms, :created_at)
                """,
                row,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Invoice {row['invoice_number']!r} is already saved."
            ) from exc

    return {"id": cursor.lastrowid, **row}


def list_invoices(client_name: str | None = None, limit: int = 20) -> list[dict]:
    """Return saved invoices, newest first, optionally filtered by client."""
    limit = max(1, min(limit, 100))
    query = "SELECT * FROM invoices"
    params: list = []
    if client_name and client_name.strip():
        query += " WHERE client_name LIKE ?"
        params.append(f"%{client_name.strip()}%")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with closing(connect()) as conn:
        return [dict(r) for r in conn.execute(query, params)]


def days_overdue(due_date: str) -> dict:
    """How many days past due_date today is (0 if not yet due)."""
    due = date.fromisoformat(parse_date(due_date, "due_date"))
    today = date.today()
    late_by = (today - due).days
    return {
        "due_date": due.isoformat(),
        "today": today.isoformat(),
        "is_overdue": late_by > 0,
        "days_overdue": max(late_by, 0),
    }
