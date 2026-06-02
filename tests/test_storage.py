import sqlite3

from swfl_event_scraper.models import Event
from swfl_event_scraper.storage import init_db, upsert_events


def test_upsert_events_writes_queryable_sqlite_records(tmp_path):
    db_path = tmp_path / "events.sqlite3"
    init_db(db_path)
    event = Event(
        title="Lakes Park Bird Patrol Walk",
        start_datetime="2026-06-06T08:00:00",
        location="Lakes Park",
        source_url="https://www.leegov.com/parks/events/event?e=demo",
        source_name="Lee County Parks & Recreation Events",
        category="Guided Walks/Tours",
        interest_flags=["civic", "parks"],
    )

    written = upsert_events(db_path, [event])

    assert written == 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("select title, source_name, interest_flags from events").fetchone()
    assert row[0] == "Lakes Park Bird Patrol Walk"
    assert row[1] == "Lee County Parks & Recreation Events"
    assert "parks" in row[2]
