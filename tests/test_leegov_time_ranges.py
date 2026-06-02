from swfl_event_scraper.parsers import parse_leegov_parks_events


def test_leegov_date_string_with_from_time_keeps_pm():
    payload = {
        "weeks": [
            {"days": [{"items": [{
                "dateString": "Wednesday, June 17, 2026 from 5:30 PM - 6:30 PM",
                "time": "5:30 PM",
                "title": "Conservation 20/20 Land Acquisition and Stewardship Advisory Committee (CLASAC)",
                "itemID": "abc",
                "ldepartTag": "Conservation 20/20 Preserves",
                "departTag": "Public meeting",
            }]}]}
        ]
    }

    events = parse_leegov_parks_events(payload, source_url="https://www.leegov.com/parks/events")

    assert events[0].start_datetime == "2026-06-17T17:30"
