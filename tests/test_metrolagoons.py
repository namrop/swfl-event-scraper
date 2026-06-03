from swfl_event_scraper.parsers import parse_metrolagoons_events_html


def test_parse_metrolagoons_brightwater_ticketed_event():
    html = """
    <div class="container flex-layout wrap">
      <div id="event-1880673" class="single-event" data-date="6/05/2026" data-type="ticketed_event">
        <figure><figcaption class="single-event__caption ticketed_event">Ticketed Event</figcaption></figure>
        <div class="single-event__content">
          <h2 class="single-event__title small">Father's Day Out (8pm - 10pm)</h2>
          <p>Tickets: General $40, Resident Member $35.</p>
        </div>
      </div>
    </div>
    """

    events = parse_metrolagoons_events_html(
        html,
        source_url="https://www.metrolagoons.com/events?lagoon=brightwater",
        lagoon_name="Brightwater Lagoon",
    )

    assert len(events) == 1
    event = events[0]
    assert event.title == "Father's Day Out (8pm - 10pm)"
    assert event.start_datetime == "2026-06-05T20:00"
    assert event.location == "Brightwater Lagoon, North Fort Myers"
    assert event.source_event_id == "1880673"
    assert event.payment_required is True
    assert event.registration_required is True
    assert event.access_type == "registration_required"
    assert event.joinability == "registration_needed"


def test_parse_metrolagoons_brightwater_day_ticket_event():
    html = """
    <div id="event-75612" class="single-event" data-date="6/01/2026" data-type="event_included_with_day_ticket">
      <figure><figcaption class="single-event__caption event_included_with_day_ticket">Event included with day ticket</figcaption></figure>
      <h2 class="single-event__title small">Movie on the Turf: Shrek (6pm)</h2>
      <p>Join us in the Hub for Movie on the Turf. Food, snacks, and drinks available for purchase.</p>
    </div>
    """

    event = parse_metrolagoons_events_html(
        html,
        source_url="https://www.metrolagoons.com/events?lagoon=brightwater",
        lagoon_name="Brightwater Lagoon",
    )[0]

    assert event.start_datetime == "2026-06-01T18:00"
    assert event.price_text == "Included with day ticket"
    assert event.payment_required is True
    assert event.access_type == "unknown"
