"""
database/db.py
──────────────
SQLite manager — stores all scraped results and prevents duplicates.
Deduplication is based on: (name + phone) OR (name + address)
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scraped.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            category    TEXT,
            rating      TEXT,
            reviews     TEXT,
            phone       TEXT,
            address     TEXT,
            website     TEXT,
            query       TEXT,
            scraped_at  TEXT
        )
    """)
    # Index for fast dedup lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_name_phone
        ON results (name, phone)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_name_address
        ON results (name, address)
    """)
    conn.commit()
    conn.close()


def is_duplicate(conn, record: dict) -> bool:
    """
    Returns True if record already exists in DB.
    Match logic:
      - Same name + same phone (if phone is not N/A)
      - OR same name + same address (if address is not N/A)
    """
    name    = (record.get("name") or "").strip()
    phone   = (record.get("phone") or "").strip()
    address = (record.get("address") or "").strip()

    if not name:
        return False

    # Check by name + phone
    if phone and phone != "N/A":
        row = conn.execute(
            "SELECT id FROM results WHERE name = ? AND phone = ?",
            (name, phone)
        ).fetchone()
        if row:
            return True

    # Check by name + address
    if address and address != "N/A":
        row = conn.execute(
            "SELECT id FROM results WHERE name = ? AND address = ?",
            (name, address)
        ).fetchone()
        if row:
            return True

    return False


def insert_record(conn, record: dict, query: str):
    """Insert a single record into DB."""
    conn.execute("""
        INSERT INTO results
            (name, category, rating, reviews, phone, address, website, query, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("name", "N/A"),
        record.get("category", "N/A"),
        record.get("rating", "N/A"),
        record.get("reviews", "N/A"),
        record.get("phone", "N/A"),
        record.get("address", "N/A"),
        record.get("website", "N/A"),
        query,
        datetime.now().isoformat()
    ))


def filter_and_store(records: list, query: str) -> dict:
    """
    Given a list of scraped records:
    1. Filter out duplicates already in DB
    2. Insert new unique records into DB
    3. Return stats + unique records only

    Returns:
        {
            "unique": [...],       # new records not seen before
            "duplicates_skipped": int,
            "total_scraped": int,
            "total_in_db": int
        }
    """
    init_db()
    conn = get_connection()

    unique    = []
    dup_count = 0

    try:
        for record in records:
            if is_duplicate(conn, record):
                dup_count += 1
            else:
                insert_record(conn, record, query)
                unique.append(record)
        conn.commit()

        total_in_db = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    finally:
        conn.close()

    return {
        "unique":             unique,
        "duplicates_skipped": dup_count,
        "total_scraped":      len(records),
        "total_in_db":        total_in_db,
    }


def get_all_records() -> list:
    """Fetch all records from DB (for full export)."""
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM results ORDER BY scraped_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_db():
    """Delete all records (reset)."""
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM results")
    conn.commit()
    conn.close() 