from __future__ import annotations

from datetime import date, datetime, timedelta
from html import unescape
import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .models import Event

DASH_RE = re.compile(r"\s*[\u2013\u2014\u2009-]+\s*")
SPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return SPACE_RE.sub(" ", unescape(value).replace("\xa0", " ")).strip()


def html_to_text(value: str | None) -> str | None:
    if not value:
        return None
    decoded = unquote(value)
    soup = BeautifulSoup(decoded, "html.parser")
    return clean_text(soup.get_text(" ")) or None


def parse_first_datetime(date_text: str, time_text: str | None = None) -> str | None:
    text = clean_text(date_text)
    if time_text:
        first_time = DASH_RE.split(clean_text(time_text))[0]
        text = f"{text} {first_time}"
    # LibraryMarket commonly repeats weekday names; dateutil tolerates them once,
    # but removing trailing weekdays makes parsing less brittle.
    text = re.sub(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", "", text, flags=re.I)
    try:
        dt = date_parser.parse(text, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    return dt.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def parse_capecoral_revize_events(payload: str | list[dict[str, Any]], source_url: str) -> list[Event]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    events: list[Event] = []
    for item in data:
        title = clean_text(item.get("title"))
        start = clean_text(item.get("start"))
        if not title or not start:
            continue
        event_url = clean_text(item.get("url")) or source_url
        events.append(
            Event(
                title=title,
                raw_title=title,
                start_datetime=start,
                end_datetime=clean_text(item.get("end")) or None,
                location=clean_text(item.get("location")) or None,
                source_url=event_url,
                source_name="Cape Coral City Calendar",
                category=clean_text(item.get("primary_calendar_name")) or None,
                description=html_to_text(item.get("desc")),
                source_event_id=clean_text(str(item.get("id") or item.get("rid") or "")) or None,
                interest_flags=["civic"] if item.get("primary_calendar_name") else [],
            )
        )
    return events


def parse_librarymarket_events(html: str, source_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article.node--type-lc-event, article.lc-event, article[class*='lc-event']")
    events: list[Event] = []
    for article in articles:
        title_link = article.select_one(".lc-event__title a, h2 a, h3 a, a[href*='/event/']")
        title = clean_text(title_link.get_text(" ") if title_link else None)
        href = title_link.get("href") if title_link else None
        date_el = article.select_one(".lc-event__date, .lc-event__month-summary, time")
        time_el = article.select_one(".lc-event-info-item--time, .lc-event__time, time")
        date_text = clean_text(date_el.get_text(" ") if date_el else "")
        time_text = clean_text(time_el.get_text(" ") if time_el else "")
        article_text = clean_text(article.get_text(" "))
        if not re.search(r"\b\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b", date_text):
            # In LibraryMarket's upcoming-card layout, `.lc-event__date` can be
            # just the time range; the month/day/year lives in the surrounding
            # card text before the title, e.g. "Jun 2 2026 Tue Title 5:30pm".
            date_match = re.search(
                r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
                r"(\d{1,2})(?:\s*-\s*\d{1,2})?\s+(\d{4})\b",
                article_text,
                flags=re.I,
            )
            if date_match:
                date_text = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}"
        start = parse_first_datetime(date_text, None if "@" in date_text else time_text)
        if not title or not start:
            continue

        branch = clean_text((article.select_one(".lc-event__branch") or article.find(string=re.compile("Library Branch:")) or "").get_text(" ") if hasattr((article.select_one(".lc-event__branch") or ""), "get_text") else "")
        if not branch:
            text = clean_text(article.get_text(" "))
            match = re.search(r"Library Branch:\s*(.+?)(?:\s+Room:|\s+Age Group:|\s+Program Type:|$)", text)
            branch = clean_text(match.group(1)) if match else ""
        branch = re.sub(r"^Library Branch:\s*", "", branch).strip() or None

        category = clean_text((article.select_one(".lc-event__program-types") or "").get_text(" ") if article.select_one(".lc-event__program-types") else "")
        if not category:
            text = clean_text(article.get_text(" "))
            match = re.search(r"Program Type:\s*(.+?)(?:\s+Details:|\s+Brief Description|$)", text)
            category = clean_text(match.group(1)) if match else ""
        category = re.sub(r"^Program Type:\s*", "", category).strip() or None

        body = article.select_one(".lc-event__body, .field--name-body")
        events.append(
            Event(
                title=title,
                raw_title=title,
                start_datetime=start,
                location=branch,
                source_url=urljoin(source_url, href) if href else source_url,
                source_name="Lee County Library System Events",
                category=category,
                description=clean_text(body.get_text(" ")) if body else None,
                source_event_id=(href.rsplit("-", 1)[-1] if href and "-" in href else href),
                interest_flags=["library", "civic"],
            )
        )
    return events


def parse_tribe_events_payload(payload: str | dict[str, Any], source_url: str, source_name: str) -> list[Event]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    events: list[Event] = []
    for item in data.get("events", []):
        title = clean_text(item.get("title"))
        start = clean_text(item.get("start_date"))
        if not title or not start:
            continue

        venue = item.get("venue") or {}
        if isinstance(venue, list):
            venue = venue[0] if venue else {}
        venue_name = clean_text(venue.get("venue") or venue.get("name")) if isinstance(venue, dict) else ""
        venue_city = clean_text(venue.get("city")) if isinstance(venue, dict) else ""
        location = ", ".join(part for part in [venue_name, venue_city] if part) or None
        categories = item.get("categories") or []
        category = ", ".join(clean_text(cat.get("name")) for cat in categories if isinstance(cat, dict) and cat.get("name")) or None
        cost = clean_text(item.get("cost"))

        event = Event(
            title=title,
            raw_title=title,
            start_datetime=start.replace(" ", "T", 1),
            end_datetime=(clean_text(item.get("end_date")).replace(" ", "T", 1) if item.get("end_date") else None),
            location=location,
            source_url=clean_text(item.get("url")) or source_url,
            source_name=source_name,
            category=category,
            description=html_to_text(item.get("description")),
            source_event_id=clean_text(str(item.get("id") or "")) or None,
            interest_flags=["civic"],
            price_text=cost or None,
        )
        event.apply_access_metadata(overwrite_unknown=True)
        events.append(event)
    return events


def parse_fort_myers_civicengage_events(html: str, source_url: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    event_blocks = soup.select('[itemscope][itemtype*="schema.org/Event"]')
    events: list[Event] = []
    for block in event_blocks:
        name_el = block.select_one('[itemprop="name"]')
        start_el = block.select_one('[itemprop="startDate"]')
        title = clean_text(name_el.get_text(" ") if name_el else None)
        start = clean_text(start_el.get_text(" ") if start_el else None)
        if not title or not start:
            continue
        parent = block.find_parent("li") or block.parent
        link = parent.find("a", href=True) if parent else None
        desc_el = block.select_one('[itemprop="description"]')
        loc_scope = block.select_one('[itemprop="location"]')
        loc_name = loc_scope.select_one('[itemprop="name"]') if loc_scope else None
        events.append(
            Event(
                title=title,
                raw_title=title,
                start_datetime=start,
                location=clean_text(loc_name.get_text(" ") if loc_name else None) or None,
                source_url=urljoin(source_url, link.get("href")) if link else source_url,
                source_name="Fort Myers CivicEngage Calendar",
                category="City calendar",
                description=clean_text(desc_el.get_text(" ") if desc_el else None) or None,
                source_event_id=(re.search(r"EID=(\d+)", link.get("href", "")).group(1) if link and re.search(r"EID=(\d+)", link.get("href", "")) else None),
                interest_flags=["civic"],
            )
        )
    return events


def enrich_event_from_civicengage_detail(event: Event, html: str) -> Event:
    soup = BeautifulSoup(html, "html.parser")
    desc_el = soup.select_one('[itemscope][itemtype*="schema.org/Event"] [itemprop="description"]')
    if desc_el:
        event.description = clean_text(desc_el.get_text(" ")) or event.description
    loc_scope = soup.select_one('[itemscope][itemtype*="schema.org/Event"] [itemprop="location"]')
    if loc_scope and not event.location:
        address = clean_text(loc_scope.get_text(" "))
        event.location = address or event.location
    event.apply_access_metadata(overwrite_unknown=True)
    return event


def parse_leegov_parks_events(payload: str | dict[str, Any], source_url: str) -> list[Event]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    events: list[Event] = []
    seen: set[str] = set()
    for week in data.get("weeks", []):
        for day in week.get("days", []):
            for item in day.get("items", []):
                title = clean_text(item.get("title"))
                item_id = clean_text(item.get("itemID"))
                if not title or not item_id or item_id in seen:
                    continue
                seen.add(item_id)
                date_text = clean_text(item.get("dateString"))
                time_text = clean_text(item.get("time"))
                # For multi-day strings, use the first date as the start.
                if " - " in date_text:
                    date_text = date_text.split(" - ", 1)[0]
                start = parse_first_datetime(
                    date_text,
                    None if re.search(r"\b(?:am|pm)\b|@", date_text, flags=re.I) else time_text,
                )
                if not start:
                    continue
                registration_value = item.get("Registration")
                registration_required = registration_value if isinstance(registration_value, bool) else None
                access_type = None
                joinability = None
                if registration_required is False:
                    access_type = "listed_event_no_registration"
                    joinability = "registration_not_required"
                elif registration_required is True:
                    access_type = "registration_required"
                    joinability = "registration_needed"
                events.append(
                    Event(
                        title=title,
                        raw_title=title,
                        start_datetime=start,
                        location=clean_text(item.get("ldepartTag")) or None,
                        source_url=f"{source_url.rstrip('/')}/event?e={item_id}",
                        source_name="Lee County Parks & Recreation Events",
                        category=clean_text(item.get("departTag")) or None,
                        description=clean_text(item.get("Description")) or None,
                        source_event_id=item_id,
                        interest_flags=["parks", "civic"],
                        registration_required=registration_required,
                        access_type=access_type,
                        joinability=joinability,
                    )
                )
    return events


WEBTRAC_READER_ITEM_RE = re.compile(
    r"\*\s+\[(?P<label>.*?)\]\((?P<url>https?://flcapecoralweb\.myvscloud\.com/[^)]*)\)",
    flags=re.S,
)
WEBTRAC_LABEL_TIME_RE = re.compile(
    r"^(?P<title>.*?)\s+(?P<start>\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(?P<end>\d{1,2}:\d{2}\s*[ap]m)$",
    flags=re.I | re.S,
)


def parse_capecoral_webtrac_reader_markdown(
    markdown: str,
    year: int,
    month: int,
    start_day: int = 1,
) -> list[Event]:
    """Parse Jina Reader markdown for Cape Coral WebTrac's calendar view.

    The WebTrac calendar itself is Cloudflare-protected for ordinary scraper
    clients. Jina's reader can fetch the public calendar page but emits a flat
    ordered bullet list without day headers. WebTrac renders events in calendar
    order and sorted by time within each day, so date boundaries are recoverable
    when the start time rolls back from evening/afternoon to morning. Current
    Cape Coral calendar pages have empty Sundays; when a rollover lands on a
    Sunday, advance to Monday so post-Saturday events stay aligned.
    """
    current_date = date(year, month, start_day)
    previous_start = None
    events: list[Event] = []
    seen: set[tuple[str, str]] = set()

    for match in WEBTRAC_READER_ITEM_RE.finditer(markdown):
        label = clean_text(match.group("label"))
        url = match.group("url")
        label_match = WEBTRAC_LABEL_TIME_RE.match(label)
        if not label_match:
            continue
        title = clean_text(label_match.group("title"))
        start_time = date_parser.parse(label_match.group("start")).time()
        end_time = date_parser.parse(label_match.group("end")).time()

        if previous_start is not None and start_time < previous_start:
            current_date += timedelta(days=1)
            if current_date.weekday() == 6:  # Sunday; current Cape WebTrac month has no Sunday entries.
                current_date += timedelta(days=1)
        previous_start = start_time

        source_event_id = parse_qs(urlparse(url).query).get("FMID", [None])[0]
        clean_url = url.split("&_csrf_token=", 1)[0]
        key = (source_event_id or clean_url, f"{current_date.isoformat()}T{start_time.isoformat(timespec='minutes')}")
        if key in seen:
            continue
        seen.add(key)

        start_dt = datetime.combine(current_date, start_time).isoformat(timespec="minutes")
        end_dt = datetime.combine(current_date, end_time).isoformat(timespec="minutes")
        events.append(
            Event(
                title=title,
                raw_title=label,
                start_datetime=start_dt,
                end_datetime=end_dt,
                source_url=clean_url,
                source_name="Cape Coral Parks WebTrac Events",
                category="Parks & Recreation",
                source_event_id=source_event_id,
                interest_flags=["parks", "civic"],
            )
        )
    return events


def parse_static_special_event_links(html: str, source_url: str) -> list[Event]:
    """Return annual/special-event links as undated civic leads.

    These are not inserted into the dated SQLite event table by default, but the
    function gives the CLI a way to report source health and future adapter work.
    """
    return []


METROLAGOONS_TIME_RE = re.compile(r"\((?P<time>\d{1,2}(?::\d{2})?\s*[ap]m(?:\s*-\s*\d{1,2}(?::\d{2})?\s*[ap]m)?)\)", re.I)


def parse_metrolagoons_events_html(html: str, source_url: str, lagoon_name: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[Event] = []
    for block in soup.select(".single-event"):
        title_el = block.select_one(".single-event__title")
        title = clean_text(title_el.get_text(" ") if title_el else None)
        date_text = clean_text(block.get("data-date"))
        if not title or not date_text:
            continue
        time_match = METROLAGOONS_TIME_RE.search(title)
        start = parse_first_datetime(date_text, time_match.group("time") if time_match else None)
        if not start:
            continue
        event_type = clean_text(block.get("data-type")).replace("_", " ") or None
        caption = clean_text((block.select_one(".single-event__caption") or "").get_text(" ") if block.select_one(".single-event__caption") else "") or event_type
        paragraphs = [clean_text(p.get_text(" ")) for p in block.select("p")]
        description = " ".join(part for part in paragraphs if part) or None
        source_event_id = clean_text((block.get("id") or "").replace("event-", "")) or None
        price_text = None
        payment_required = None
        registration_required = None
        access_type = None
        joinability = None
        normalized_type = (block.get("data-type") or "").lower()
        caption_text = (caption or "").lower()
        if "ticketed" in normalized_type or "ticketed" in caption_text:
            price_text = "Ticketed event"
            payment_required = True
            registration_required = True
            access_type = "registration_required"
            joinability = "registration_needed"
        elif "included" in normalized_type or "included" in caption_text:
            price_text = "Included with day ticket"
            payment_required = True
        elif "resident" in normalized_type or "resident" in caption_text:
            price_text = "Resident member event"

        event = Event(
            title=title,
            raw_title=title,
            start_datetime=start,
            location=f"{lagoon_name}, North Fort Myers",
            source_url=source_url,
            source_name=f"MetroLagoons {lagoon_name} Events",
            category=caption or "Lagoon event",
            description=description,
            source_event_id=source_event_id,
            interest_flags=["venue", "north_fort_myers"],
            price_text=price_text,
            payment_required=payment_required,
            registration_required=registration_required,
            access_type=access_type,
            joinability=joinability,
        )
        event.apply_access_metadata(overwrite_unknown=True)
        events.append(event)
    return events


def parse_generic_jsonld_events(html: str, source_url: str, source_name: str = "") -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[Event] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") != "Event":
                continue
            title = clean_text(item.get("name"))
            start = clean_text(item.get("startDate"))
            if not title or not start:
                continue
            location = item.get("location")
            loc = location.get("name") if isinstance(location, dict) else None
            events.append(
                Event(
                    title=title,
                    start_datetime=start,
                    location=clean_text(loc) or None,
                    source_url=clean_text(item.get("url")) or source_url,
                    source_name=source_name,
                    category="Event",
                    description=clean_text(item.get("description")) or None,
                )
            )
    return events
