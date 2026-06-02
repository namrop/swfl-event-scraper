from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

from .models import Event

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
    scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_name);
CREATE INDEX IF NOT EXISTS idx_events_interest ON events(interest_flags) WHERE interest_flags IS NOT NULL;
"""

UPSERT_SQL = """
INSERT INTO events (
    id, title, start_datetime, end_datetime, location, source_url, source_name,
    category, description, raw_title, source_event_id, interest_flags, is_spam
) VALUES (
    :id, :title, :start_datetime, :end_datetime, :location, :source_url, :source_name,
    :category, :description, :raw_title, :source_event_id, :interest_flags, :is_spam
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
    last_seen_at=datetime('now');
"""


def init_db(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_events(path: str | Path, events: Iterable[Event]) -> int:
    rows = [event.as_record() for event in events]
    if not rows:
        return 0
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(UPSERT_SQL, rows)
    return len(rows)
