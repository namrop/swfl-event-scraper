from swfl_event_scraper.parsers import parse_tribe_events_payload


def test_parse_tribe_events_payload_marks_public_meeting():
    payload = {
        "events": [
            {
                "id": 30383,
                "title": "Council Meeting",
                "url": "https://estero-fl.gov/events/council-meeting-12/",
                "description": "<p>Council meetings are open to the public.</p>",
                "start_date": "2026-06-03 09:30:00",
                "end_date": "2026-06-03 09:30:00",
                "venue": [],
                "categories": [{"name": "Council Meeting"}],
                "cost": "",
            }
        ]
    }

    events = parse_tribe_events_payload(payload, "https://estero-fl.gov", "Village of Estero Events")

    assert len(events) == 1
    event = events[0]
    assert event.title == "Council Meeting"
    assert event.start_datetime == "2026-06-03T09:30:00"
    assert event.source_event_id == "30383"
    assert event.category == "Council Meeting"
    assert event.access_type == "public_meeting"
    assert event.joinability == "public_attendance_ok"
