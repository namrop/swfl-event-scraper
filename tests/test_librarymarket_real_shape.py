from swfl_event_scraper.parsers import parse_librarymarket_events


def test_librarymarket_recovers_date_when_date_class_only_contains_time():
    html = """
    <article class="node node--type-lc-event">
      <div>This event is in the "Adults" group Jun 2 2026 Tue</div>
      <h3 class="lc-event__title"><a href="/event/english-cafe-1">English Café</a></h3>
      <div class="lc-event__date">6:00pm–7:30pm</div>
      <div class="lc-event-info-item--time">6:00pm–7:30pm</div>
      <div class="lc-event__branch">Library Branch: Cape Coral-Lee County Public Library</div>
    </article>
    """

    events = parse_librarymarket_events(html, source_url="https://leelibrary.librarymarket.com/events/upcoming")

    assert events[0].start_datetime == "2026-06-02T18:00"
