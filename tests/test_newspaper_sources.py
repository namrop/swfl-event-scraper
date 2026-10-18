"""Florida Weekly (evvnt calendar) and Cape Coral Breeze (community listings).

Fixtures are real responses captured 2026-10-17, trimmed to the fields and
markup the adapters read.
"""

from datetime import date
import json
from pathlib import Path

from swfl_event_scraper.parsers import (
    parse_breeze_article,
    parse_breeze_feed,
    parse_evvnt_events,
)

FIXTURES = Path(__file__).parent / "fixtures"
FW_URL = "https://www.floridaweekly.com/events/ft-myers/"
FW_NAME = "Florida Weekly Fort Myers Events"
BREEZE_NAME = "Cape Coral Breeze Community Listings"


def _fw_events():
    payload = json.loads((FIXTURES / "evvnt_florida_weekly_page.json").read_text())
    return parse_evvnt_events(payload, source_url=FW_URL, source_name=FW_NAME)


def _breeze(name, published):
    html = (FIXTURES / f"breeze_{name}.html").read_text()
    url = f"https://www.capecoralbreeze.com/news/community-news/2026/10/16/{name}/"
    return parse_breeze_article(html, url=url, source_name=BREEZE_NAME, published=published)


# --- Florida Weekly / evvnt ------------------------------------------------


def test_evvnt_local_times_venue_and_link():
    events = _fw_events()
    assert len(events) == 3
    red = events[0]
    assert red.title == "Lee County's Red Ribbon Award Celebration"
    # evvnt gives offset timestamps; the ledger convention is naive local time.
    assert red.start_datetime == "2026-10-26T18:30:00"
    assert red.end_datetime == "2026-10-26T20:00:00"
    assert red.location == "Collaboratory, 2031 Jackson Street, Fort Myers"
    assert red.source_url.startswith("https://www.floridaweekly.com/events/ft-myers/?_evDiscoveryPath=/event/3871764")
    assert red.source_event_id == "3871764"
    assert red.category == "Local / Community"
    assert "free and open to the public" in (red.description or "")
    assert red.source_name == FW_NAME


def test_evvnt_prices_become_a_range():
    crawl = _fw_events()[1]
    assert crawl.price_amount_min == 10.99
    assert crawl.price_amount_max == 14.99
    assert crawl.price_text == "$10.99-$14.99"
    assert crawl.price_currency == "USD"
    assert crawl.payment_required is True


def test_evvnt_free_price_and_backfill_provenance():
    payload = {
        "rawEvents": [
            {
                "title": "Monofilament Madness",
                "start_time": "2026-10-31T08:00:00-04:00",
                "end_time": "2026-10-31T13:00:00-04:00",
                "venue": {"name": "Salty Sam's Marina", "address_1": None, "town": "Fort Myers Beach"},
                "prices": {"Free": "USD 0.0"},
                "sources": ["evvnt"],
                "source_id_s": "1",
                "category_name": "Outdoors",
            }
        ]
    }
    (event,) = parse_evvnt_events(payload, source_url=FW_URL, source_name=FW_NAME)
    assert event.price_text == "Free"
    assert event.payment_required is False
    assert event.location == "Salty Sam's Marina, Fort Myers Beach"
    # Submitted straight to the paper: no "via" tag.
    assert not [flag for flag in event.interest_flags if flag.startswith("via_")]

    walden = _fw_events()[2]
    # Backfilled by evvnt from Bandsintown: keep where it came from.
    assert "via_bandsintown" in walden.interest_flags
    assert walden.category.endswith("via Bandsintown")


# --- Cape Coral Breeze -----------------------------------------------------


def test_breeze_single_event_article():
    (event,) = _breeze("sunset-fest-set-for-wednesday", date(2026, 10, 16))
    assert event.title == "Sunset Fest set for Wednesday"
    assert event.start_datetime == "2026-10-21T16:00:00"
    assert event.end_datetime == "2026-10-21T19:00:00"
    assert event.location == "Four Freedoms Park, 4818 Tarpon Court, Cape Coral"
    assert event.source_name == BREEZE_NAME
    assert "live music, food trucks" in event.description


def test_breeze_time_in_a_later_paragraph_and_the_is_at_line():
    (event,) = _breeze("ccfw-to-hold-forum-for-city-candidates", date(2026, 10, 16))
    assert event.title == "CCFW to hold forum for city candidates"
    assert event.start_datetime == "2026-10-20T18:30:00"
    assert event.end_datetime is None
    assert event.location == "Rotary Park Environmental Center, 5505 Rose Garden Road, Cape Coral"


def test_breeze_venue_schedule_splits_items_and_dates():
    events = _breeze("this-week-at-the-buck-oct-14-20", date(2026, 10, 13))
    got = sorted((e.start_datetime, e.end_datetime, e.title) for e in events)
    assert got == [
        ("2026-10-14T20:00:00", "2026-10-14T23:00:00", "Live Music with Tommy Lee Cook & The Buckingham Blues Band"),
        ("2026-10-17T14:00:00", "2026-10-17T19:00:00",
         "Backyard Blues Fest with Albert Castiglia, Tommy Lee Cook & The Buckingham Blues Band, and Big Al & The Heavyweights"),
        ("2026-10-18T15:00:00", "2026-10-18T18:00:00", "Live Music with Tommy Lee Cook & The Buckingham Blues Band"),
    ]
    # The venue is only named in the footer block.
    assert {e.location for e in events} == {"Buckingham Blues Bar, 5641 Buckingham Road, Fort Myers"}
    blues = [e for e in events if e.title.startswith("Backyard")][0]
    assert blues.price_amount_min == 30.0 and blues.price_amount_max == 35.0


def test_breeze_community_calendar_roundup():
    events = _breeze("community-calendar-may-1", date(2026, 4, 30))
    by_date = {e.start_datetime[:10]: e for e in events}
    assert sorted(by_date) == ["2026-05-04", "2026-05-06", "2026-05-09"]

    toast = by_date["2026-05-04"]
    assert toast.title == "Cape Chapter #9051 of Toastmasters International open house Monday"
    assert (toast.start_datetime, toast.end_datetime) == ("2026-05-04T18:00:00", "2026-05-04T20:00:00")
    assert toast.location.startswith("Providence Christian Church, 701 Mohawk Parkway")

    computer = by_date["2026-05-06"]
    assert (computer.start_datetime, computer.end_datetime) == ("2026-05-06T14:00:00", "2026-05-06T16:00:00")
    assert computer.location == "Online (Zoom)"

    bingo = by_date["2026-05-09"]
    assert (bingo.start_datetime, bingo.end_datetime) == ("2026-05-09T16:00:00", "2026-05-09T20:00:00")
    assert bingo.location == "American Legion Post 90, 1401 S.E. 47th St., Cape Coral"
    # A class "every Thursday in May" carries no single date and is not invented.
    assert not [e for e in events if "cha-cha" in e.title]


def test_breeze_past_dates_and_results_stories_yield_nothing():
    html = (
        "<html><body><h1>Tennis tourney raises funds</h1>"
        "<div id='single_meta'><h5><time>Oct 14, 2026</time></h5></div>"
        "<div id='article_content_wrap'><p>The tournament was held Saturday, Oct. 10, at the club.</p>"
        "<p>Organizers said next year's event is planned.</p></div></body></html>"
    )
    assert parse_breeze_article(html, url="https://x/", source_name=BREEZE_NAME) == []


def test_breeze_news_story_past_dates_do_not_roll_forward():
    # Captured 2026-10-17. The story names March 12, 2025, Dec. 3, "closed on
    # March 3" and April 28 as history, then the meeting itself. Only the
    # meeting is an event, and "at Risk approach" is not a place.
    (event,) = _breeze("council", date(2026, 10, 14))
    assert event.title == "City council to revisit road improvements for North 3 UEP"
    assert event.start_datetime == "2026-10-14T09:00:00"
    assert event.location == "1015 Cultural Park Blvd., Cape Coral"


def test_breeze_each_date_keeps_its_own_site():
    # Captured 2026-10-17: one article, four dates, four different sites.
    events = _breeze("flu-vaccinations-available-in-community", date(2026, 10, 16))
    got = [(e.start_datetime, e.end_datetime, e.location) for e in sorted(events, key=lambda e: e.start_datetime)]
    assert got == [
        ("2026-10-17T14:00:00", "2026-10-17T16:00:00",
         "Cape Coral Bootstrap Homeless Ministry inside the Messiah Lutheran Church, 2691 N.E. Pine Island Road, Cape Coral"),
        ("2026-10-24T10:00:00", "2026-10-24T14:00:00",
         "Cape Coral Hospital Auxiliary’s Car Show & Health Fair, 609 S.E. 13th Court, Cape Coral"),
        ("2026-10-27T12:30:00", "2026-10-27T15:00:00", "Lake Kennedy Senior Center, 400 Santa Barbara Blvd. S., Cape Coral"),
        ("2026-10-29T10:30:00", "2026-10-29T12:30:00", "East United Way Resiliency Hub, 4040 Palm Beach Blvd., Suite C, Fort Myers"),
    ]
    assert {e.title for e in events} == {"Flu vaccinations available in community"}


def test_breeze_december_article_reaches_january():
    html = (
        "<html><body><h1>New Year's Day plunge</h1>"
        "<div id='single_meta'><h5><time>Dec 20, 2026</time></h5></div>"
        "<div id='article_content_wrap'><p>The plunge is at 10 a.m. Friday, Jan. 1, at Yacht Club Beach.</p>"
        "</div></body></html>"
    )
    (event,) = parse_breeze_article(html, url="https://x/plunge/", source_name=BREEZE_NAME)
    assert event.start_datetime == "2027-01-01T10:00:00"
    assert event.location == "Yacht Club Beach"


def test_breeze_skips_columns_and_opinion():
    from swfl_event_scraper.scrape import breeze_article_wanted

    assert breeze_article_wanted("https://www.capecoralbreeze.com/news/community-news/2026/10/16/sunset-fest/")
    assert not breeze_article_wanted(
        "https://www.capecoralbreeze.com/sports/sports-columns/2026/10/16/fishing-with-capt-george-tunison/"
    )


def test_breeze_feed_items():
    xml = (
        "<?xml version='1.0'?><rss><channel>"
        "<item><title>Sunset Fest set for Wednesday</title>"
        "<link>https://www.capecoralbreeze.com/news/community-news/2026/10/16/sunset-fest-set-for-wednesday/</link>"
        "<pubDate>Fri, 16 Oct 2026 15:59:55 +0000</pubDate></item>"
        "</channel></rss>"
    )
    (item,) = parse_breeze_feed(xml)
    assert item["title"] == "Sunset Fest set for Wednesday"
    assert item["link"].endswith("/sunset-fest-set-for-wednesday/")
    assert item["published"] == date(2026, 10, 16)
