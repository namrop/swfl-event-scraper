# SWFL Event Scraper

Standalone local scraper for Cape Coral / Fort Myers / Lee County events.

The v0 bias is civic usefulness over ticketing coverage: government calendars,
parks & recreation, libraries, and public civic events are first-class sources,
with Eventbrite treated as only one optional source.

## What it scrapes now

Working request-based adapters:

- Cape Coral official city Revize calendar (`capecoral.gov/calendar.php`) — Events + Public Meetings via the Revize JSON data handler.
- Lee County Parks & Recreation (`leegov.com/parks/events`) — SharePoint CalendarWS endpoint, including parks, guided walks, sports tournaments, and Conservation 20/20 meetings.
- Lee County Library System (`leelibrary.librarymarket.com/events/upcoming`) — LibraryMarket upcoming-event cards.
- Fort Myers official CivicEngage calendar (`fortmyers.gov/calendar.aspx`) — schema.org microdata in event and meeting calendar pages.

Tracked but pending adapters:

- Cape Coral Parks WebTrac event calendar — official Parks & Rec calendar, currently Cloudflare-blocked for plain HTTP requests; needs browser adapter or endpoint discovery.
- Cape Coral Special Events hub — annual-event landing pages; needs event-date extraction per linked event site.
- Eventbrite — optional ticketed source, intentionally not the center of coverage.

## Run

```bash
PYTHONPATH=src python3 -m swfl_event_scraper.cli --db data/events.sqlite3 --json
```

Output is a JSON scrape-health summary and a SQLite database at `data/events.sqlite3`.

## Query examples

```bash
sqlite3 data/events.sqlite3 \
  "select title, start_datetime, location, source_name from events order by start_datetime limit 20;"

sqlite3 data/events.sqlite3 \
  "select source_name, count(*) from events group by source_name order by count(*) desc;"
```

## Tests

```bash
python3 -m pytest tests -q
```
