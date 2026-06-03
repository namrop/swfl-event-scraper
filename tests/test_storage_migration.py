import sqlite3

from swfl_event_scraper.storage import init_db

OLD_SCHEMA = """
CREATE TABLE events (
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
)
"""


def test_init_db_migrates_and_backfills_access_metadata_for_existing_rows(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(OLD_SCHEMA)
        conn.execute(
            """
            insert into events (
                id, title, start_datetime, source_url, source_name, category,
                description, interest_flags
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "existing-row",
                "Open Pickleball Play",
                "2026-06-08T12:00",
                "https://example.test/pickleball",
                "Cape Coral Parks WebTrac Events",
                "Parks & Recreation",
                None,
                '["parks"]',
            ),
        )

    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "select access_type, joinability, registration_required from events where id='existing-row'"
        ).fetchone()
    assert row == ("drop_in", "drop_in_ok", 0)
