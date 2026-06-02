from swfl_event_scraper.parsers import parse_capecoral_webtrac_reader_markdown


def test_parse_webtrac_reader_markdown_assigns_dates_by_calendar_rollover():
    markdown = """
Title: Event Calendar

Markdown Content:
*   [Camp Cuties 6:30 am - 6:00 pm](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=164969389&Module=AR&_csrf_token=abc)
*   [Yoga 9:00 am - 10:00 am](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=165372464&Module=AR&_csrf_token=abc)
*   [Youth Basketball 12U 6:00 pm - 9:30 pm](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=168345700&Module=AR&_csrf_token=abc)
*   [School's Out Youth Center 6:30 am - 6:00 pm](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=158452022&Module=AR&_csrf_token=abc)
*   [Open Pickleball Play 12:00 pm - 3:00 pm](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=165378646&Module=AR&_csrf_token=abc)
"""

    events = parse_capecoral_webtrac_reader_markdown(markdown, year=2026, month=6)

    assert [event.title for event in events] == [
        "Camp Cuties",
        "Yoga",
        "Youth Basketball 12U",
        "School's Out Youth Center",
        "Open Pickleball Play",
    ]
    assert events[0].start_datetime == "2026-06-01T06:30"
    assert events[2].start_datetime == "2026-06-01T18:00"
    assert events[3].start_datetime == "2026-06-02T06:30"
    assert events[3].source_event_id == "158452022"


def test_parse_webtrac_reader_markdown_skips_empty_sundays_when_calendar_rolls_over():
    markdown = """
*   [Saturday Class 9:00 am - 10:00 am](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=1&Module=AR)
*   [Monday Camp 6:30 am - 6:00 pm](https://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=detail&FMID=2&Module=AR)
"""

    events = parse_capecoral_webtrac_reader_markdown(markdown, year=2026, month=6, start_day=6)

    assert events[0].start_datetime == "2026-06-06T09:00"
    assert events[1].start_datetime == "2026-06-08T06:30"
