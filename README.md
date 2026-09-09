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
- Village of Estero events (`estero-fl.gov/wp-json/tribe/events/v1`) — official WordPress/The Events Calendar API for village meetings, workshops, closures, and civic/special events.
- MetroLagoons Brightwater Lagoon (`metrolagoons.com/events?lagoon=brightwater`) — North Fort Myers venue events via the public AJAX event-calendar endpoint; events can be included-with-day-ticket, ticketed, or resident-member-only.
- FGCU Events (`fgcu.edu/calendar`) — official Florida Gulf Coast University events via the public FGCU/25Live JSON feed.
- FSW Presence Events (`fsw.presence.io/events`) — official Florida SouthWestern State College event calendar via the public Presence JSON API.

Tracked but pending adapters:

- Cape Coral Special Events hub — annual-event landing pages; needs event-date extraction per linked event site.
- Bonita Springs City Calendar and City Approved Events — official CivicLive/React calendar surfaces are tracked, but still need a stable request adapter for the portlet/export flow.
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
- `access_type` (`drop_in`, `public_meeting`, `registration_required`, `class_series`, `listed_event_no_registration`, `unknown`)
- `joinability` (`drop_in_ok`, `public_attendance_ok`, `registration_needed`, `verify_mid_session_joinability`, `registration_not_required`, `unknown`)

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

---

## Sol migration, 2026-09-09 — the ledger

This repo moved from Acubens to Sol on 2026-09-09 and its output moved from a
machine-local SQLite into an append-only ledger in the Atrium. The Acubens copy
is retired, not deleted (`RETIRED_2026-09-09.md` there).

SQLite is still the working store — the tests cover it and the scrape path is
unchanged. What is new is a `ledger-append` step that folds the ledger to
latest-row-per-id and appends only what is new or actually different.

```bash
# scrape into SQLite only (the old behaviour; bare flags still work)
PYTHONPATH=src python3 -m swfl_event_scraper.cli scrape --json

# scrape, then append new/changed rows to the Atrium ledger
PYTHONPATH=src python3 -m swfl_event_scraper.cli ledger-append

# what is worth doing in the next fortnight, widening if the week is thin
PYTHONPATH=src python3 -m swfl_event_scraper.cli query \
    --min-rating 3 --since 2026-09-10 --radius-mi 15 --widen-until 12

# Luis tunes the searcher
PYTHONPATH=src python3 -m swfl_event_scraper.cli feedback <id> +1 --note "yes"
PYTHONPATH=src python3 -m swfl_event_scraper.cli feedback <id> -1 --note "campus only"

PYTHONPATH=src python3 -m swfl_event_scraper.cli health
```

The row contract, the fold rule, the rating formula and the radius ladder are
written up in canon at
`12_runtime/ledgers/events/event_candidates_row_contract_v1.md`. The interest
vocabulary is `src/swfl_event_scraper/vocabulary/interest_tags.yaml`, data
rather than code, with the canon path each tag was read off.

Scheduled on Sol as Hermes cron job `541cbcda7679`, Tuesday and Friday 03:10 ET,
through `20_digital_architecture/household_newspaper/scripts/events_ledger_append.py`.

### Sources added 2026-09-09

Live: Florida Repertory Theatre, Alliance for the Arts (which also carries
Theatre Conspiracy and the GreenMarket), Naples Botanical Garden — all three
through the existing Events Calendar REST adapter.

Declared and not fetched, each with the probed reason in its `notes`: Barbara B.
Mann, Broadway Palm, Cultural Park Theatre, Laboratory Theater, Sidney & Berne
Davis, Theatre Conspiracy, Gulfshore Playhouse, The Naples Players, Artis—Naples
(robots.txt Disallow, honoured), Collier County Public Library, Eventbrite.

Cape Coral Parks WebTrac is now a `fetch: browser_lane` source: Cloudflare
blocks every request client by fingerprint, so the adapter reads a grid dump
produced by an Earthglass Chrome lane on 40eridani rather than fetching. Point
`SWFL_WEBTRAC_DUMP` at the saved HTML.
