# SWFL Event Scraper

Standalone local scraper for Cape Coral / Fort Myers / Lee County events.

The v0 bias is civic usefulness over ticketing coverage: government calendars,
parks & recreation, libraries, and public civic events are first-class sources,
with Eventbrite treated as only one optional source.

## What it scrapes now

Working request-based adapters:

- Cape Coral official city Revize calendar (`capecoral.gov/calendar.php`) — Events + Public Meetings via the Revize JSON data handler.
- Cape Coral Parks WebTrac (`myvscloud.com`) — direct requests hit Cloudflare, so v0 uses `r.jina.ai` as a read-only public text-reader fallback for the public calendar page. This currently yields the full visible month.
- Lee County Parks & Recreation (`leegov.com/parks/events`) — SharePoint CalendarWS endpoint, including parks, guided walks, sports tournaments, and Conservation 20/20 meetings.
- Lee County Library System (`leelibrary.librarymarket.com/events/upcoming`) — LibraryMarket upcoming-event cards.
- Fort Myers official CivicEngage calendar (`fortmyers.gov/calendar.aspx`) — schema.org microdata in event and meeting calendar pages.

Tracked but pending adapters:

- Cape Coral Special Events hub — annual-event landing pages; needs event-date extraction per linked event site.
- Eventbrite — optional ticketed source, intentionally not the center of coverage.

## Run

```bash
PYTHONPATH=src python3 -m swfl_event_scraper.cli --db data/events.sqlite3 --json
```

Output is a JSON scrape-health summary and a SQLite database at `data/events.sqlite3`.

The event table includes explicit triage fields for the practical planning layer:

- `price_text`, `price_amount_min`, `price_amount_max`, `price_currency`
- `payment_required`
- `registration_required`
- `access_type` (`drop_in`, `registration_required`, `class_series`, `unknown`)
- `joinability` (`drop_in_ok`, `registration_needed`, `verify_mid_session_joinability`, `unknown`)

These are conservative metadata fields. If a source does not expose exact price or enrollment state, the scraper preserves unknowns and flags likely class-series items for manual/open-registration verification instead of treating them as drop-in events.

## Query examples

```bash
sqlite3 data/events.sqlite3 \
  "select title, start_datetime, location, source_name from events order by start_datetime limit 20;"

sqlite3 data/events.sqlite3 \
  "select title, start_datetime, price_text, access_type, joinability from events order by start_datetime limit 20;"

sqlite3 data/events.sqlite3 \
  "select access_type, joinability, count(*) from events group by access_type, joinability order by count(*) desc;"
```

## Tests

```bash
python3 -m pytest tests -q
```
