"""Florida Weekly's weekly column, "What to do, where to go", and the curation weight.

Fixtures are the real column pages of 2026-09-29 and 2026-10-13 and the
column's section page, captured 2026-10-18 and trimmed to the article body.
Luis, 2026-10-18: "I want that article read. those are curated events from a
person. worth rating higher."
"""

from pathlib import Path

from swfl_event_scraper.interest import load_vocabulary, rate
from swfl_event_scraper.parsers import parse_fw_column_article, parse_fw_column_index
from swfl_event_scraper.rows import candidate_from_event
from swfl_event_scraper.sources import SOURCES

FIXTURES = Path(__file__).parent / "fixtures"
SECTION = "https://www.floridaweekly.com/fort-myers/arts-entertainment/what-to-do-where-to-go/"
OCT13 = (
    "https://www.floridaweekly.com/fort-myers/live-music-and-tribute-shows-highlight-fort-myers-events/"
    "article_5b8d3731-6e82-4581-89b5-e1413ded05e7.html"
)
SEP29 = (
    "https://www.floridaweekly.com/fort-myers/what-to-do-this-week-for-live-music-and-local-events-guide/"
    "article_b5c74494-35fd-4df1-9eb2-9198c852702b.html"
)
NAME = "Florida Weekly — What to do, where to go"


def _column(fixture, url):
    html = (FIXTURES / fixture).read_text()
    return parse_fw_column_article(html, url=url, source_name=NAME)


def _by_title(events, title):
    found = [e for e in events if e.title == title]
    assert found, f"no event titled {title!r}; have {sorted({e.title for e in events})}"
    return found


def test_index_finds_the_column_and_nothing_else():
    html = (FIXTURES / "fw_column_section_2026-10-18.html").read_text()
    assert parse_fw_column_index(html, base_url=SECTION) == [OCT13]


def test_dated_listing_with_time_venue_address_and_price():
    events = _column("fw_column_2026-10-13.html", OCT13)
    (ai,) = _by_title(events, "FGCU Academy Lecture: The Rise of AI")
    assert ai.start_datetime == "2026-10-14T13:30:00"
    assert ai.end_datetime is None
    assert ai.location == "Sidney & Berne Davis Art Center, 2301 First St., Fort Myers"
    assert (ai.price_amount_min, ai.price_amount_max, ai.price_text) == (42.0, 42.0, "$42")
    assert ai.payment_required is True
    assert "live ChatGPT demo" in ai.description
    assert "sbdac.com" not in ai.description
    assert ai.source_url == OCT13
    assert ai.source_name == NAME
    assert {"florida_weekly", "fw_column"} <= set(ai.interest_flags)


def test_two_showtimes_take_the_first_and_noon_is_noon():
    events = _column("fw_column_2026-10-13.html", OCT13)
    (cowgirls,) = _by_title(events, "Rhinestone Cowgirls")
    assert cowgirls.start_datetime == "2026-10-15T14:00:00"
    assert cowgirls.category == "Live performance"
    assert (cowgirls.price_amount_min, cowgirls.price_amount_max, cowgirls.price_text) == (76.0, None, "From $76")
    (block,) = _by_title(events, "Oktoberfest Block Party")
    assert block.start_datetime == "2026-10-17T12:00:00"
    assert block.location == "Bay Street Yard, 2136 Bay Street, Fort Myers"


def test_no_time_stated_keeps_a_bare_date():
    events = _column("fw_column_2026-10-13.html", OCT13)
    (walk,) = _by_title(events, "21st Annual Walk to Prevent Child Abuse")
    assert walk.start_datetime == "2026-10-17"
    assert walk.location == "Bell Tower Shops, 13499 S Cleveland Ave., Fort Myers"
    assert walk.price_amount_min == 30.0


def test_free_listings():
    events = _column("fw_column_2026-10-13.html", OCT13)
    for title in ("Gulf Coast Youth Orchestra Fall Concert", "Elvis Through the Years"):
        (event,) = _by_title(events, title)
        assert event.price_text == "Free", title
        assert event.payment_required is False, title


def test_ongoing_runs_with_stated_dates_and_none_without():
    events = _column("fw_column_2026-10-13.html", OCT13)
    (radium,) = _by_title(events, "Radium Girls")
    assert (radium.start_datetime, radium.end_datetime) == ("2026-10-16", "2026-10-25")
    assert radium.location == "Cultural Park Theatre, 528 Cultural Park Blvd., Cape Coral"
    (shark,) = _by_title(events, "The Shark is Broken")
    assert (shark.start_datetime, shark.end_datetime) == ("2026-10-16", "2026-11-14")
    (nerd,) = _by_title(events, "The Nerd")
    assert (nerd.start_datetime, nerd.end_datetime) == ("2026-10-20", "2026-11-15")
    octo = sorted(_by_title(events, "Oktoberfest Cape Coral"), key=lambda e: e.start_datetime)
    assert [(e.start_datetime, e.end_datetime) for e in octo] == [
        ("2026-10-16", "2026-10-18"),
        ("2026-10-23", "2026-10-25"),
    ]
    titles = {e.title for e in events}
    # A recurrence ("every Sunday"), a run with only an end ("through Oct.
    # 25") and nights with no dates yield nothing rather than a guessed date.
    for absent in ("Fort Myers Farmers Market", "The Pillowman", "Babcock Ranch’s Halloween Nights", "Rooftop Yoga"):
        assert absent not in titles, absent


def test_top_picks_tag_their_listing_or_stand_alone():
    events = _column("fw_column_2026-10-13.html", OCT13)
    picks = {e.title for e in events if "fw_top_pick" in e.interest_flags}
    assert picks == {"Oktoberfest Cape Coral", "Farmer Mike’s 12th Annual Fall Festival", "The Shark is Broken"}
    # Farmer Mike's runs "every weekend", so only the pick's own date stands.
    (mike,) = _by_title(events, "Farmer Mike’s 12th Annual Fall Festival")
    assert mike.start_datetime == "2026-10-17"
    assert mike.location == "Farmer Mike’s U-Pick of Bonita Springs, 26031 Morton Ave., Bonita Springs"


def test_photo_captions_are_not_events_and_the_count_is_exact():
    events = _column("fw_column_2026-10-13.html", OCT13)
    titles = {e.title for e in events}
    for caption in ("Oktoberfest", "Shark", "Views of Pumpkins from the patch at Farmer Mike's Bonita Springs."):
        assert caption not in titles
    # 32 dated listings (Wed 2, Thu 3, Fri 7, Sat 11, Sun 7, Mon 1, Tue 1),
    # 9 ongoing runs with stated dates (Oktoberfest Cape Coral twice), and
    # one top pick that has no other row.
    assert len(events) == 42


def test_older_layout_slash_dates_and_unheaded_picks():
    events = _column("fw_column_2026-09-29.html", SEP29)
    (bell,) = _by_title(events, "Belltober Pub crawl")
    assert bell.start_datetime == "2026-10-02T18:00:00"
    assert "fw_top_pick" in bell.interest_flags
    (art,) = _by_title(events, "Art Walk")
    assert art.start_datetime == "2026-10-02T17:00:00"
    assert art.location.startswith("Downtown Fort Myers’ River District")
    (frank,) = _by_title(events, "Frank and Dean Live")
    assert frank.start_datetime == "2026-10-03T13:00:00"
    (parrot,) = _by_title(events, "ParrotPhest")
    assert (parrot.start_datetime, parrot.end_datetime) == ("2026-10-01", "2026-10-04")
    assert "fw_top_pick" in parrot.interest_flags
    # "at Margaritaville Beach Resort Oct. 1-4 with ...": the dates are not the venue.
    assert parrot.location.startswith("Margaritaville Beach Resort, ")
    # 36 dated listings and 4 ongoing runs; the three picks all match a row.
    assert len(events) == 40
    assert not [e for e in events if "COURTESY PHOTO" in e.title]


def test_december_column_reaches_january():
    html = (
        "<html><body><h1>What to do, where to go</h1>"
        "<time datetime='2026-12-29T17:00:00-05:00'>Dec 29, 2026</time>"
        "<div id='article-body'><h2>FRIDAY 1.1</h2>"
        "<p>New Year’s Day Plunge – Beach event at Lynn Hall Memorial Park at 10 a.m. Start the year in the Gulf. "
        "950 Estero Blvd., Fort Myers Beach. fortmyersbeachfl.gov .</p></div></body></html>"
    )
    (plunge,) = parse_fw_column_article(html, url="https://x/article_1.html", source_name=NAME)
    assert plunge.start_datetime == "2027-01-01T10:00:00"
    assert plunge.location == "Lynn Hall Memorial Park, 950 Estero Blvd., Fort Myers Beach"


# --- curation ---------------------------------------------------------------


def test_curation_weight_lives_in_the_vocabulary():
    assert load_vocabulary()["curation"]["weight"] > 0


def test_a_pick_rates_higher_and_says_who_picked_it():
    weight = load_vocabulary()["curation"]["weight"]
    plain = rate(title="Radium Girls", description="A gripping true-story drama.", distance_mi=5.0)
    picked = rate(
        title="Radium Girls",
        description="A gripping true-story drama.",
        distance_mi=5.0,
        curated_by="Florida Weekly staff",
    )
    assert picked.rating == round(min(5.0, plain.rating + weight), 1)
    assert "picked by Florida Weekly staff" in picked.rating_reason
    assert "picked by" not in plain.rating_reason


def test_a_pick_does_not_lift_a_hard_exclusion():
    picked = rate(title="Belltober Pub crawl", description="Sip seasonal drinks.", distance_mi=5.0,
                  curated_by="Florida Weekly staff")
    assert picked.rating <= 0.5


def test_the_column_source_is_curated_and_the_calendar_is_not():
    by_name = {s.name: s for s in SOURCES}
    column = by_name[NAME]
    assert column.curated_by
    assert by_name["Florida Weekly Fort Myers Events"].curated_by is None
    events = _column("fw_column_2026-10-13.html", OCT13)
    (radium,) = _by_title(events, "Radium Girls")
    row = candidate_from_event(radium, column)
    assert "picked by" in row["rating_reason"]
