from swfl_event_scraper.parsers import (
    parse_capecoral_webtrac_grid_html,
    strip_webtrac_csrf,
)

GRID = """
<table><tr>
<td>
  <div class="calendar__day-label-long">September 12, 2026</div>
  <a class="calendar__block" data-state-item="112233"
     aria-label="Open Pickleball&#10;9:00 am - 11:00 am"
     href="/webtrac/web/search.html?display=detail&amp;FMID=112233&amp;Module=AR&amp;_csrf_token=deadbeef">x</a>
  <a class="calendar__block" data-state-item="112233"
     aria-label="Open Pickleball&#10;9:00 am - 11:00 am"
     href="/webtrac/web/search.html?FMID=112233&amp;_csrf_token=deadbeef">dupe</a>
  <a class="calendar__block" data-state-item="445566"
     aria-label="Yoga in the Park"
     href="/webtrac/web/search.html?display=detail&amp;FMID=445566">y</a>
</td>
<td><div class="calendar__day-label-long">September 13, 2026</div>
  <a class="calendar__block" data-state-item="112233"
     aria-label="Open Pickleball&#10;9:00 am - 11:00 am" href="/x">z</a>
</td>
</tr></table>
"""


def test_grid_parses_dates_times_and_fmids():
    events = parse_capecoral_webtrac_grid_html(GRID, source_url="https://example.invalid")
    # The duplicate (FMID, start) pair is dropped; the same FMID on another day is kept.
    assert len(events) == 3
    pickleball = [e for e in events if e.title == "Open Pickleball"]
    assert len(pickleball) == 2
    assert pickleball[0].start_datetime.startswith("2026-09-12T09:00")
    assert pickleball[0].end_datetime.startswith("2026-09-12T11:00")
    assert pickleball[0].source_event_id == "112233"
    yoga = [e for e in events if e.title == "Yoga in the Park"][0]
    assert yoga.start_datetime.startswith("2026-09-12T00:00")
    assert yoga.end_datetime is None


def test_csrf_token_never_reaches_the_row():
    events = parse_capecoral_webtrac_grid_html(GRID, source_url="https://example.invalid")
    assert all("_csrf_token" not in e.source_url for e in events)
    assert strip_webtrac_csrf("https://h/x?a=1&_csrf_token=zz&b=2") == "https://h/x?a=1&b=2"
