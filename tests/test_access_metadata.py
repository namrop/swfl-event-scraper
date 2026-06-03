import sqlite3

from swfl_event_scraper.models import Event, infer_access_metadata
from swfl_event_scraper.storage import init_db, upsert_events


def test_infer_access_metadata_classifies_free_drop_in_and_price_amounts():
    free = infer_access_metadata(
        title="Free Nature Seminars at Rotary Park",
        description="Drop in for a free one-hour talk. No registration required.",
        category="Parks & Recreation",
    )
    assert free["price_text"] == "Free"
    assert free["payment_required"] is False
    assert free["registration_required"] is False
    assert free["access_type"] == "drop_in"
    assert free["joinability"] == "drop_in_ok"

    paid = infer_access_metadata(
        title="Introduction to Pottery with Erica Klopf",
        description="Registration required. Fee: $45 residents / $55 non-residents.",
        category="Parks & Recreation",
    )
    assert paid["price_text"] == "$45-$55"
    assert paid["price_amount_min"] == 45.0
    assert paid["price_amount_max"] == 55.0
    assert paid["payment_required"] is True
    assert paid["registration_required"] is True
    assert paid["access_type"] == "registration_required"


def test_infer_access_metadata_marks_program_classes_as_mid_session_risk_when_price_unknown():
    metadata = infer_access_metadata(
        title="Yoga Essentials",
        description=None,
        category="Parks & Recreation",
        source_name="Cape Coral Parks WebTrac Events",
    )

    assert metadata["price_text"] is None
    assert metadata["payment_required"] is None
    assert metadata["registration_required"] is None
    assert metadata["access_type"] == "class_series"
    assert metadata["joinability"] == "verify_mid_session_joinability"


def test_event_record_and_sqlite_preserve_access_metadata(tmp_path):
    db_path = tmp_path / "events.sqlite3"
    event = Event(
        title="Beginner Line Dance with Leigh",
        start_datetime="2026-06-08T18:45",
        source_url="https://example.test/line-dance",
        source_name="Cape Coral Parks WebTrac Events",
        category="Parks & Recreation",
        description="Registration required. $12 per class.",
    )

    assert event.price_text == "$12"
    assert event.payment_required is True
    assert event.registration_required is True
    assert event.access_type == "registration_required"

    init_db(db_path)
    written = upsert_events(db_path, [event])

    assert written == 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            select price_text, price_amount_min, price_amount_max, payment_required,
                   registration_required, access_type, joinability
            from events
            """
        ).fetchone()
    assert row == ("$12", 12.0, 12.0, 1, 1, "registration_required", "registration_needed")
