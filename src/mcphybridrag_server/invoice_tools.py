"""Invoice storage in SQLite, plus overdue-date helpers."""

import json
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
    extra_details  TEXT,    -- JSON object: any other fields printed on the invoice
    created_at     TEXT    NOT NULL
)
"""

# Main columns; extra_details must not repeat these.
MAIN_FIELDS = {
    "id",
    "client_name",
    "invoice_number",
    "issue_date",
    "due_date",
    "total_amount",
    "currency",
    "late_fee_terms",
    "created_at",
}
MAX_EXTRA_KEYS = 50
MAX_EXTRA_CHARS = 8000


def connect() -> sqlite3.Connection:
    """Open the database and make sure the table exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute(SCHEMA)
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a DB row to a dict, decoding extra_details back from JSON."""
    data = dict(row)
    if data.get("extra_details"):
        data["extra_details"] = json.loads(data["extra_details"])
    return data


def clean_extra_details(extra: dict | str | None) -> str | None:
    """Validate extra invoice fields and return them as a JSON string.

    Anything goes as long as it is a flat-ish JSON object of invoice data.
    Keys that repeat a main column and empty values are dropped.
    """
    if not extra:
        return None
    if isinstance(extra, str):
        # LLMs sometimes send the object as a JSON string, or plain text.
        try:
            extra = json.loads(extra)
        except json.JSONDecodeError:
            extra = {"notes": extra}
    if not isinstance(extra, dict):
        raise ValueError("extra_details must be an object of field: value pairs.")

    cleaned = {
        str(key).strip(): value
        for key, value in extra.items()
        if str(key).strip()
        and str(key).strip().lower() not in MAIN_FIELDS
        and value not in (None, "", [], {})
    }
    if not cleaned:
        return None
    if len(cleaned) > MAX_EXTRA_KEYS:
        raise ValueError(f"extra_details has more than {MAX_EXTRA_KEYS} fields.")

    text = json.dumps(cleaned, ensure_ascii=False)
    if len(text) > MAX_EXTRA_CHARS:
        raise ValueError(f"extra_details is too large (max {MAX_EXTRA_CHARS} chars).")
    return text


DATE_ORDER = os.getenv("INVOICE_DATE_ORDER", "DMY").upper()

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d %b %Y",  # 05 Jan 2026
    "%d %B %Y",  # 05 January 2026
    "%b %d, %Y",  # Jan 05, 2026
    "%B %d, %Y",  # January 05, 2026
] + (
    ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]
    if DATE_ORDER == "DMY"
    else ["%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y"]
)


def parse_date(value: str | None, field: str) -> str | None:
    """Normalise a date to YYYY-MM-DD; empty means not provided.

    Small LLMs often copy dates as printed (e.g. 20/01/2026) instead of
    converting them, so common formats are accepted here.
    """
    if not value or not value.strip():
        return None
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"{field} must be a date like YYYY-MM-DD, got {value!r}")


def save_invoice(
    client_name: str,
    total_amount: float,
    due_date: str | None = None,
    invoice_number: str | None = None,
    issue_date: str | None = None,
    currency: str | None = None,
    late_fee_terms: str | None = None,
    extra_details: dict | str | None = None,
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
        "extra_details": clean_extra_details(extra_details),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    # closing() closes the connection; "with conn" commits (or rolls back).
    with closing(connect()) as conn, conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO invoices (client_name, invoice_number, issue_date,
                    due_date, total_amount, currency, late_fee_terms,
                    extra_details, created_at)
                VALUES (:client_name, :invoice_number, :issue_date,
                    :due_date, :total_amount, :currency, :late_fee_terms,
                    :extra_details, :created_at)
                """,
                row,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Invoice {row['invoice_number']!r} is already saved."
            ) from exc

    saved = {"id": cursor.lastrowid, **row}
    if saved["extra_details"]:
        saved["extra_details"] = json.loads(saved["extra_details"])
    return saved


def list_invoices(client_name: str | None = None, limit: int = 20) -> list[dict]:
    """Return saved invoices, newest first, optionally filtered by client."""
    # LLMs sometimes send 0 or junk for "no limit"; treat that as the default.
    limit = min(limit, 100) if limit and limit > 0 else 20
    query = "SELECT * FROM invoices"
    params: list = []
    if client_name and client_name.strip():
        query += " WHERE client_name LIKE ?"
        params.append(f"%{client_name.strip()}%")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with closing(connect()) as conn:
        return [row_to_dict(r) for r in conn.execute(query, params)]


def get_invoice(invoice_number: str) -> dict:
    """Return one invoice by its invoice number (case-insensitive)."""
    if not invoice_number or not invoice_number.strip():
        raise ValueError("invoice_number cannot be empty.")

    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT * FROM invoices WHERE invoice_number = ? COLLATE NOCASE",
            (invoice_number.strip(),),
        ).fetchone()

    if row is None:
        raise ValueError(f"No saved invoice with number {invoice_number!r}.")
    return row_to_dict(row)


def list_overdue_invoices() -> dict:
    """Return invoices whose due date is before today, most overdue first."""
    # Use the local date from Python; SQLite's date('now') is UTC.
    today = date.today()

    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE due_date < ? ORDER BY due_date",
            (today.isoformat(),),
        ).fetchall()

    invoices = [
        {**row_to_dict(r), "days_overdue": (today - date.fromisoformat(r["due_date"])).days}
        for r in rows
    ]
    return {"today": today.isoformat(), "count": len(invoices), "invoices": invoices}


def invoices_due_between(start_date: str, end_date: str) -> dict:
    """Return invoices with a due date from start_date to end_date (inclusive)."""
    start = parse_date(start_date, "start_date")
    end = parse_date(end_date, "end_date")
    if not start or not end:
        raise ValueError("start_date and end_date are both required.")
    if start > end:
        start, end = end, start  # forgive reversed ranges

    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE due_date BETWEEN ? AND ? ORDER BY due_date",
            (start, end),
        ).fetchall()

    invoices = [row_to_dict(r) for r in rows]
    return {
        "start_date": start,
        "end_date": end,
        "count": len(invoices),
        "invoices": invoices,
    }


def total_due_by_client(client_name: str) -> dict:
    """Sum invoice amounts for a client, grouped by currency."""
    if not client_name or not client_name.strip():
        raise ValueError("client_name cannot be empty.")

    with closing(connect()) as conn:
        rows = conn.execute(
            """
            SELECT currency, COUNT(*) AS invoice_count, SUM(total_amount) AS total
            FROM invoices
            WHERE client_name LIKE ?
            GROUP BY currency
            """,
            (f"%{client_name.strip()}%",),
        ).fetchall()

    # Amounts in different currencies can't be added together, so keep
    # one total per currency.
    totals = [
        {
            "currency": r["currency"] or "unknown",
            "invoice_count": r["invoice_count"],
            "total": round(r["total"], 2),
        }
        for r in rows
    ]
    return {
        "client_name": client_name.strip(),
        "invoice_count": sum(t["invoice_count"] for t in totals),
        "totals": totals,
    }


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
