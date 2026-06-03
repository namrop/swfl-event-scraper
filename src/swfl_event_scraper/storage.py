from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

from .models import Event, infer_access_metadata

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_datetime TEXT NOT NULL,
    end_datetime TEXT,
    location TEXT,
    source_url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    raw_title TEXT,
    source_event_id TEXT,
    interest_flags TEXT,
    is_spam INTEGER DEFAULT 0,
    price_text TEXT,
    price_amount_min REAL,
    price_amount_max REAL,
    price_currency TEXT,
    payment_required INTEGER,
    registration_required INTEGER,
    access_type TEXT,
    joinability TEXT,
    scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_name);
CREATE INDEX IF NOT EXISTS idx_events_interest ON events(interest_flags) WHERE interest_flags IS NOT NULL;
"""

ACCESS_METADATA_COLUMNS = {
    "price_text": "TEXT",
    "price_amount_min": "REAL",
    "price_amount_max": "REAL",
    "price_currency": "TEXT",
    "payment_required": "INTEGER",
    "registration_required": "INTEGER",
    "access_type": "TEXT",
    "joinability": "TEXT",
}

UPSERT_SQL = """
INSERT INTO events (
    id, title, start_datetime, end_datetime, location, source_url, source_name,
    category, description, raw_title, source_event_id, interest_flags, is_spam,
    price_text, price_amount_min, price_amount_max, price_currency,
    payment_required, registration_required, access_type, joinability
) VALUES (
    :id, :title, :start_datetime, :end_datetime, :location, :source_url, :source_name,
    :category, :description, :raw_title, :source_event_id, :interest_flags, :is_spam,
    :price_text, :price_amount_min, :price_amount_max, :price_currency,
    :payment_required, :registration_required, :access_type, :joinability
)
ON CONFLICT(id) DO UPDATE SET
    title=excluded.title,
    start_datetime=excluded.start_datetime,
    end_datetime=excluded.end_datetime,
    location=excluded.location,
    source_url=excluded.source_url,
    source_name=excluded.source_name,
    category=excluded.category,
    description=excluded.description,
    raw_title=excluded.raw_title,
    source_event_id=excluded.source_event_id,
    interest_flags=excluded.interest_flags,
    is_spam=excluded.is_spam,
    price_text=excluded.price_text,
    price_amount_min=excluded.price_amount_min,
    price_amount_max=excluded.price_amount_max,
    price_currency=excluded.price_currency,
    payment_required=excluded.payment_required,
    registration_required=excluded.registration_required,
    access_type=excluded.access_type,
    joinability=excluded.joinability,
    last_seen_at=datetime('now');
"""


def backfill_access_metadata(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, title, description, category, source_name
        FROM events
        WHERE access_type IS NULL
           OR access_type = 'unknown'
           OR joinability IS NULL
           OR joinability = 'unknown'
           OR price_text IS NULL
           OR payment_required IS NULL
           OR registration_required IS NULL
        """
    ).fetchall()
    for row_id, title, description, category, source_name in rows:
        metadata = infer_access_metadata(title, description, category, source_name)
        conn.execute(
            """
            UPDATE events
            SET price_text = COALESCE(price_text, :price_text),
                price_amount_min = COALESCE(price_amount_min, :price_amount_min),
                price_amount_max = COALESCE(price_amount_max, :price_amount_max),
                price_currency = COALESCE(price_currency, :price_currency),
                payment_required = COALESCE(payment_required, :payment_required),
                registration_required = COALESCE(registration_required, :registration_required),
                access_type = CASE
                    WHEN access_type IS NULL OR access_type = 'unknown' THEN :access_type
                    ELSE access_type
                END,
                joinability = CASE
                    WHEN joinability IS NULL OR joinability = 'unknown' THEN :joinability
                    ELSE joinability
                END
            WHERE id = :id
            """,
            {
                "id": row_id,
                "price_text": metadata["price_text"],
                "price_amount_min": metadata["price_amount_min"],
                "price_amount_max": metadata["price_amount_max"],
                "price_currency": metadata["price_currency"],
                "payment_required": None
                if metadata["payment_required"] is None
                else int(metadata["payment_required"]),
                "registration_required": None
                if metadata["registration_required"] is None
                else int(metadata["registration_required"]),
                "access_type": metadata["access_type"],
                "joinability": metadata["joinability"],
            },
        )


def init_db(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
        for column, column_type in ACCESS_METADATA_COLUMNS.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE events ADD COLUMN {column} {column_type}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_price ON events(price_amount_min) WHERE price_amount_min IS NOT NULL"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_access_type ON events(access_type)")
        backfill_access_metadata(conn)


def upsert_events(path: str | Path, events: Iterable[Event]) -> int:
    rows = [event.as_record() for event in events]
    if not rows:
        return 0
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(UPSERT_SQL, rows)
    return len(rows)
