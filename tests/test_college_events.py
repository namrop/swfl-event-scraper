from swfl_event_scraper.parsers import parse_fgcu_25live_events, parse_presence_events
from swfl_event_scraper.scrape import filter_presence_events_for_current_window
from swfl_event_scraper.sources import SOURCES, SourceKind


def test_parse_fgcu_25live_all_events_payload_normalizes_event_fields():
    payload = [
        {
            "eventID": 1397122215,
            "template": "Eagle View Orientation",
            "title": "EVO: WELCOME TO FGCU",
            "description": "<p>College is exciting. <strong>Register online</strong>.</p>",
            "location": '<a href="http://maps.google.com/?q=26.465807,-81.772062">Cohen Student Union Ballroom</a>',
            "startDateTime": "2026-06-04T09:00:00",
            "endDateTime": "2026-06-04T09:20:00",
            "canceled": False,
            "requiresPayment": False,
            "openSignUp": True,
            "categoryCalendar": "Special Events",
            "customFields": [
                {"label": "Organization", "value": "EAGLE VIEW ORIENTATION"},
                {"label": "Registration", "value": '<a href="https://www.fgcu.edu/orientation/">Register</a>'},
            ],
            "permaLinkUrl": "https://www.fgcu.edu/events/event/?1397122215/test-special-events/evo-welcome-to-fgcu",
        }
    ]

    events = parse_fgcu_25live_events(payload, "https://www.fgcu.edu/calendar/", "FGCU Events")

    assert len(events) == 1
    event = events[0]
    assert event.title == "EVO: WELCOME TO FGCU"
    assert event.start_datetime == "2026-06-04T09:00:00"
    assert event.end_datetime == "2026-06-04T09:20:00"
    assert event.location == "Cohen Student Union Ballroom"
    assert event.source_name == "FGCU Events"
    assert event.category == "Special Events, Eagle View Orientation"
    assert event.description == "College is exciting. Register online. Registration: Register"
    assert event.source_event_id == "1397122215"
    assert event.registration_required is True
    assert event.access_type == "registration_required"
    assert event.joinability == "registration_needed"


def test_parse_presence_events_converts_utc_to_local_and_preserves_access_signals():
    payload = [
        {
            "eventNoSqlId": "fe0adae9-3d8e-4967-b51b-b6685e980f00",
            "uri": "one-blood-blood-drive-lee-4",
            "eventName": "One Blood Blood Drive - Lee",
            "organizationName": "Recreation & Wellness",
            "description": "<p>To make an appointment, register online. We also accept walk ins.</p>",
            "location": "Lee Campus Lot 12",
            "startDateTimeUtc": "2026-08-26T13:00:00Z",
            "endDateTimeUtc": "2026-08-26T19:00:00Z",
            "rsvpStatus": 1,
            "isRsvpLimited": False,
            "tags": ["Community Engagement", "Lee Campus"],
        }
    ]

    events = parse_presence_events(payload, "https://fsw.presence.io/events", "FSW Presence Events")

    assert len(events) == 1
    event = events[0]
    assert event.title == "One Blood Blood Drive - Lee"
    assert event.start_datetime == "2026-08-26T09:00:00"
    assert event.end_datetime == "2026-08-26T15:00:00"
    assert event.location == "Lee Campus Lot 12"
    assert event.source_url == "https://fsw.presence.io/event/one-blood-blood-drive-lee-4"
    assert event.source_name == "FSW Presence Events"
    assert event.category == "Recreation & Wellness, Community Engagement, Lee Campus"
    assert event.source_event_id == "fe0adae9-3d8e-4967-b51b-b6685e980f00"
    assert event.registration_required is True
    assert event.access_type == "registration_required"
    assert event.joinability == "registration_needed"


def test_presence_fetch_filter_drops_events_that_have_already_ended():
    payload = [
        {
            "eventName": "Old Event",
            "startDateTimeUtc": "2026-05-19T14:00:00Z",
            "endDateTimeUtc": "2026-05-19T16:00:00Z",
        },
        {
            "eventName": "In Progress Event",
            "startDateTimeUtc": "2026-06-05T13:00:00Z",
            "endDateTimeUtc": "2026-06-05T17:00:00Z",
        },
        {
            "eventName": "Future Event",
            "startDateTimeUtc": "2026-08-26T13:00:00Z",
            "endDateTimeUtc": "2026-08-26T19:00:00Z",
        },
    ]

    filtered = filter_presence_events_for_current_window(payload, now_utc="2026-06-05T15:00:00Z")

    assert [item["eventName"] for item in filtered] == ["In Progress Event", "Future Event"]


def test_sources_include_fgcu_and_fsw_college_surfaces():
    college_sources = [source for source in SOURCES if source.kind is SourceKind.COLLEGE]
    names = {source.name for source in college_sources}

    assert "FGCU Events" in names
    assert "FSW Presence Events" in names
