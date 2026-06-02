from swfl_event_scraper.parsers import parse_leegov_parks_events


def test_parse_leegov_parks_calendarws_payload():
    payload = {
        "month": 6,
        "year": 2026,
        "weeks": [
            {
                "days": [
                    {
                        "day": 6,
                        "month": 6,
                        "year": 2026,
                        "items": [
                            {
                                "dateString": "Saturday, June 6, 2026",
                                "time": "8:00 AM",
                                "title": "Lakes Park Bird Patrol Walk",
                                "itemID": "7909E7910E876.0.2026-06-06T12%3A00%3A00Z",
                                "ldepartTag": "Parks - Lakes Park",
                                "departTag": "Guided Walks/Tours",
                                "Description": "Monthly birding tour.",
                            }
                        ],
                    }
                ]
            }
        ],
    }

    events = parse_leegov_parks_events(payload, source_url="https://www.leegov.com/parks/events")

    assert len(events) == 1
    assert events[0].title == "Lakes Park Bird Patrol Walk"
    assert events[0].start_datetime == "2026-06-06T08:00"
    assert events[0].location == "Parks - Lakes Park"
    assert events[0].category == "Guided Walks/Tours"
    assert events[0].source_url.endswith("event?e=7909E7910E876.0.2026-06-06T12%3A00%3A00Z")
