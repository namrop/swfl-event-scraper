from swfl_event_scraper.parsers import (
    parse_capecoral_revize_events,
    parse_fort_myers_civicengage_events,
    parse_librarymarket_events,
)


def test_parse_capecoral_revize_events_decodes_city_calendar_json():
    payload = [
        {
            "title": "Red, White & BOOM",
            "primary_calendar_name": "Events",
            "calendar_displays": ["1"],
            "start": "2026-07-04T17:00:00",
            "end": "2026-07-04T22:00:00",
            "url": "https://www.capeboom.com/",
            "location": "Cape Coral Parkway",
            "desc": "%3Cp%3EFree citywide special event%3C%2Fp%3E",
            "id": "boom-2026",
        }
    ]

    events = parse_capecoral_revize_events(payload, source_url="https://www.capecoral.gov/calendar.php")

    assert len(events) == 1
    assert events[0].title == "Red, White & BOOM"
    assert events[0].category == "Events"
    assert events[0].start_datetime == "2026-07-04T17:00:00"
    assert "citywide" in events[0].description


def test_parse_librarymarket_events_from_upcoming_cards():
    html = """
    <article class="node node--type-lc-event">
      <h3 class="lc-event__title"><a href="/event/book-club-123">First Tuesday on First Street Book Club</a></h3>
      <div class="lc-event__date"><span>Jun 2 2026 Tue</span></div>
      <div class="lc-event-info-item--time">5:30pm–6:30pm</div>
      <div class="lc-event__branch">Library Branch: Fort Myers Regional Library</div>
      <div class="lc-event__program-types">Program Type: Book Discussion</div>
      <div class="lc-event__body">Meet new people and discuss books.</div>
    </article>
    """

    events = parse_librarymarket_events(html, source_url="https://leelibrary.librarymarket.com/events/upcoming")

    assert len(events) == 1
    assert events[0].title == "First Tuesday on First Street Book Club"
    assert events[0].location == "Fort Myers Regional Library"
    assert events[0].category == "Book Discussion"
    assert events[0].start_datetime.startswith("2026-06-02T17:30")


def test_parse_fort_myers_civicengage_microdata():
    html = """
    <li>
      <h3><a href="/Calendar.aspx?EID=6860&month=6&year=2026&day=2&calType=0"><span>Red, White & Blue Golf Day</span></a></h3>
      <div class="subHeader"><div class="date">June 14, 2026, 7:00 AM - 6:00 PM</div></div>
      <div class="hidden" itemscope itemtype="http://schema.org/Event">
        <span itemprop="name">Red, White & Blue Golf Day</span>
        <span itemprop="startDate" class="hidden">2026-06-14T07:00:00</span>
        <p itemprop="description">Parks month event at city golf facilities.</p>
        <span itemprop="location" itemscope itemtype="http://schema.org/Place"><span itemprop="name">Fort Myers Country Club</span></span>
      </div>
    </li>
    """

    events = parse_fort_myers_civicengage_events(html, source_url="https://fortmyers.gov/calendar.aspx")

    assert len(events) == 1
    assert events[0].title == "Red, White & Blue Golf Day"
    assert events[0].location == "Fort Myers Country Club"
    assert events[0].start_datetime == "2026-06-14T07:00:00"
