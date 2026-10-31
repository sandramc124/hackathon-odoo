"""Database connection + small helpers shared by every module.

Changes to this file go through the team leader only.
"""
import os
from contextlib import contextmanager

import psycopg2
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from flask import request
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/subscription_db"
)


class ApiError(Exception):
    """Raise anywhere in a route; app.py turns it into a JSON error response."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


@contextmanager
def transaction():
    """Yields a cursor; commits on success, rolls back on any exception."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_all(sql, params=()):
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=()):
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=()):
    """Runs a write. Returns the first row if the SQL has RETURNING, else None."""
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.fetchone() if cur.description else None


def update_fields(table, pk_col, pk_val, data, allowed):
    """UPDATE only whitelisted columns. `table`/`pk_col`/`allowed` are code constants."""
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        raise ApiError("No valid fields to update")
    sets = ", ".join(f"{k} = %s" for k in fields)
    row = execute(
        f"UPDATE {table} SET {sets} WHERE {pk_col} = %s RETURNING *",
        (*fields.values(), pk_val),
    )
    if not row:
        raise ApiError(f"{table} record not found", 404)
    return row


def json_body():
    return request.get_json(silent=True) or {}


def require_fields(data, *fields):
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ApiError(f"Missing required field(s): {', '.join(missing)}")


_CYCLES = {
    "weekly": lambda n: relativedelta(weeks=n),
    "monthly": lambda n: relativedelta(months=n),
    "quarterly": lambda n: relativedelta(months=3 * n),
    "yearly": lambda n: relativedelta(years=n),
}


def add_cycle(start_date, billing_cycle, n=1):
    """start_date + n billing cycles (used for end_date and next_billing_date)."""
    return start_date + _CYCLES[billing_cycle](n)
