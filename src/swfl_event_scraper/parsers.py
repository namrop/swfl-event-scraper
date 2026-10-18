from __future__ import annotations

from datetime import date, datetime, timedelta
from html import unescape
import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .models import Event

DASH_RE = re.compile(r"\s*[\u2013\u2014\u2009-]+\s*")
SPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = SPACE_RE.sub(" ", unescape(value).replace("\xa0", " ")).strip()
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


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


def parse_fgcu_25live_events(payload: str | list[dict[str, Any]], source_url: str, source_name: str) -> list[Event]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    events: list[Event] = []
    for item in data:
        title = clean_text(item.get("title"))
        start = clean_text(item.get("startDateTime"))
        if not title or not start:
            continue
        if item.get("canceled") and not title.lower().startswith("canceled"):
            title = f"CANCELED - {title}"

        custom_fields = item.get("customFields") or []
        custom_by_label: dict[str, str] = {}
        for field in custom_fields:
            if not isinstance(field, dict):
                continue
            label = clean_text(field.get("label"))
            value = html_to_text(field.get("value")) or clean_text(field.get("value"))
            if label and value:
                custom_by_label[label.lower()] = value

        description_parts = [html_to_text(item.get("description"))]
        if custom_by_label.get("registration"):
            description_parts.append(f"Registration: {custom_by_label['registration']}")
        description = " ".join(part for part in description_parts if part) or None

        category_parts = [clean_text(item.get("categoryCalendar")) or clean_text(item.get("template"))]
        organization = custom_by_label.get("organization")
        if organization:
            category_parts.append(organization.title())
        category = ", ".join(part for part in category_parts if part) or None

        payment_required = True if item.get("requiresPayment") is True else None
        registration_required = True if item.get("openSignUp") or custom_by_label.get("registration") else None
        event = Event(
            title=title,
            raw_title=clean_text(item.get("title")) or title,
            start_datetime=start,
            end_datetime=clean_text(item.get("endDateTime")) or None,
            location=html_to_text(item.get("location")) or None,
            source_url=clean_text(item.get("permaLinkUrl") or item.get("webLink")) or source_url,
            source_name=source_name,
            category=category,
            description=description,
            source_event_id=clean_text(str(item.get("eventID") or "")) or None,
            interest_flags=["college", "fgcu"],
            price_text="Payment required" if payment_required else None,
            payment_required=payment_required,
            registration_required=registration_required,
            access_type="registration_required" if registration_required else None,
            joinability="registration_needed" if registration_required else None,
        )
        event.apply_access_metadata(overwrite_unknown=True)
        events.append(event)
    return events


def _presence_local_datetime(utc_value: str | None) -> str | None:
    text = clean_text(utc_value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = parse_first_datetime(text)
        return parsed.replace("+00:00", "") if parsed else None
    return dt.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None).isoformat(timespec="seconds")


def parse_presence_events(payload: str | list[dict[str, Any]], source_url: str, source_name: str) -> list[Event]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    events: list[Event] = []
    for item in data:
        title = clean_text(item.get("eventName") or item.get("title"))
        start = _presence_local_datetime(item.get("startDateTimeUtc") or item.get("start"))
        if not title or not start:
            continue

        tags = [clean_text(tag) for tag in item.get("tags") or [] if clean_text(tag)]
        category_parts = [clean_text(item.get("organizationName")), *tags]
        rsvp_status = item.get("rsvpStatus")
        registration_required = True if item.get("isRsvpLimited") or rsvp_status not in (None, -1, 2) else None
        event = Event(
            title=title,
            raw_title=title,
            start_datetime=start,
            end_datetime=_presence_local_datetime(item.get("endDateTimeUtc") or item.get("end")),
            location=clean_text(item.get("location")) or None,
            source_url=urljoin(source_url, f"/event/{clean_text(item.get('uri'))}") if item.get("uri") else source_url,
            source_name=source_name,
            category=", ".join(part for part in category_parts if part) or None,
            description=html_to_text(item.get("description")),
            source_event_id=clean_text(item.get("eventNoSqlId") or item.get("uri")) or None,
            interest_flags=["college", "fsw"],
            registration_required=registration_required,
            access_type="registration_required" if registration_required else None,
            joinability="registration_needed" if registration_required else None,
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


# ---------------------------------------------------------------------------
# Cape Coral Parks WebTrac — browser-lane grid dump
# ---------------------------------------------------------------------------
#
# WebTrac has been unreadable since June: Cloudflare blocks by client
# fingerprint, so curl, requests and the r.jina.ai reader all get 403 from
# Sol and from Acubens' residential IP alike, and the site publishes no iCal
# or RSS. The recovery lane got the data on 2026-09-09 through an Earthglass
# Chrome lane on 40eridani — 496 occurrences, 127 titles — and the method is
# written up at
# 20_digital_architecture/the_masthead/cape_coral_webtrac_recovery_2026-09-09.md.
#
# This parser therefore takes a PRE-FETCHED dump rather than fetching. The
# browser lane saves the calendar grid's HTML; this reads it. Nothing here
# touches the network, which is the point: the fetch is a separate, browser-
# shaped act on a different host.
#
# Grid shape, per the recovery report:
#   td  ->  .calendar__day-label-long   the exact date
#   a.calendar__block                    one occurrence
#       aria-label   "<title>\n<time range>"
#       data-state-item                  the FMID
#       href                             the detail URL, carrying a session
#                                        _csrf_token that must be stripped
#
# FMIDs recur, so the caller dedupes on (FMID, start_datetime).

WEBTRAC_CSRF_RE = re.compile(r"[?&]_csrf_token=[^&]*", re.I)
WEBTRAC_TIME_RE = re.compile(
    r"(\d{1,2}:\d{2}\s*[apAP]\.?[mM]\.?)\s*(?:-|–|to)\s*(\d{1,2}:\d{2}\s*[apAP]\.?[mM]\.?)"
)


def strip_webtrac_csrf(url: str) -> str:
    """Session state must not be stored in a ledger row's source_url."""
    return WEBTRAC_CSRF_RE.sub("", url or "")


def parse_capecoral_webtrac_grid_html(
    html: str,
    source_url: str,
    source_name: str = "Cape Coral Parks WebTrac Events",
) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[Event] = []
    seen: set[tuple[str, str]] = set()

    for cell in soup.find_all("td"):
        label = cell.select_one(".calendar__day-label-long")
        if not label:
            continue
        try:
            day = date_parser.parse(clean_text(label.get_text()))
        except (ValueError, OverflowError):
            continue
        for block in cell.select("a.calendar__block"):
            # The newline inside aria-label is the title/time separator, so the
            # raw attribute is split BEFORE whitespace is collapsed. Some blocks
            # carry no newline; there the time range itself is the boundary.
            aria_raw = block.get("aria-label") or block.get_text() or ""
            parts = [p.strip() for p in re.split(r"[\n\r]+", aria_raw) if p.strip()]
            if len(parts) > 1:
                title, time_text = clean_text(parts[0]), " ".join(parts[1:])
            else:
                flat = clean_text(aria_raw)
                split = WEBTRAC_TIME_RE.search(flat)
                title = clean_text(flat[: split.start()]) if split else flat
                time_text = flat[split.start():] if split else ""
            aria = clean_text(aria_raw)
            if not title:
                continue
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            end = None
            match = WEBTRAC_TIME_RE.search(time_text)
            if match:
                iso_day = day.date().isoformat()
                try:
                    start = date_parser.parse(f"{iso_day} {match.group(1)}")
                    end = date_parser.parse(f"{iso_day} {match.group(2)}")
                except (ValueError, OverflowError):
                    end = None
            fmid = clean_text(block.get("data-state-item") or "")
            key = (fmid, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            href = block.get("href") or source_url
            if href.startswith("/"):
                href = "https://flcapecoralweb.myvscloud.com" + href
            events.append(
                Event(
                    title=title,
                    raw_title=aria,
                    start_datetime=start.isoformat(),
                    end_datetime=end.isoformat() if end else None,
                    location="Cape Coral Parks & Recreation",
                    source_url=strip_webtrac_csrf(href),
                    source_name=source_name,
                    category="Parks & Recreation",
                    source_event_id=fmid or None,
                    interest_flags=["civic"],
                )
            )
    return events


# ---------------------------------------------------------------------------
# Florida Weekly — the evvnt calendar behind floridaweekly.com/events
# ---------------------------------------------------------------------------
#
# Added 2026-10-17 (Luis: "adding the newspaper to the event scraper").
# Florida Weekly's online events calendar is an evvnt discovery widget,
# publisher 12336 ("Fort Myers - Florida Weekly"). The widget reads a public
# JSON endpoint on discovery.evvnt.com, which is what the adapter reads too;
# floridaweekly.com itself rate-limits plain clients (HTTP 429).
#
# Rows come from two places, and every row says which in `sources`: events
# submitted to the paper (`evvnt`) and evvnt's backfill from Bandsintown,
# AXS, Ticketmaster, RunSignUp and others, which the paper has switched on
# and shows on its own calendar. Backfilled rows are kept, tagged `via_<x>`
# and labelled in the category, so the ledger can tell them apart.

EVVNT_SOURCE_LABELS = {
    "bandsintown": "Bandsintown",
    "axs": "AXS",
    "ticketmaster": "Ticketmaster",
    "run_sign_up": "RunSignUp",
    "active_network": "Active Network",
    "event_vesta": "EventVesta",
    "eventbrite": "Eventbrite",
    "meetup": "Meetup",
    "goldstar": "Goldstar",
}


def _local_naive(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return parse_first_datetime(text)
    if dt.tzinfo is not None:
        dt = dt.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds")


def _evvnt_prices(prices: Any) -> tuple[float | None, float | None]:
    if not isinstance(prices, dict):
        return None, None
    amounts: list[float] = []
    for value in prices.values():
        match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
        if match:
            amounts.append(float(match.group(1)))
    if not amounts:
        return None, None
    return min(amounts), max(amounts)


def parse_evvnt_events(payload: str | dict[str, Any], source_url: str, source_name: str) -> list[Event]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    events: list[Event] = []
    for item in data.get("rawEvents") or []:
        title = clean_text(item.get("title"))
        start = _local_naive(item.get("start_time"))
        if not title or not start:
            continue

        venue = item.get("venue") or {}
        if item.get("online_only"):
            location = "Online"
        else:
            name = clean_text(venue.get("name"))
            address = clean_text(venue.get("address_1"))
            town = clean_text(venue.get("town"))
            parts = [name]
            if address and address != name:
                parts.append(address)
            parts.append(town)
            location = ", ".join(part for part in parts if part) or None

        upstream = [str(s) for s in item.get("sources") or [] if s and s != "evvnt"]
        category = clean_text(item.get("category_name")) or None
        if upstream:
            via = ", ".join(EVVNT_SOURCE_LABELS.get(s, s) for s in upstream)
            category = f"{category} · via {via}" if category else f"via {via}"

        low, high = _evvnt_prices(item.get("prices"))
        if low is None:
            price_text = None
            payment_required = None
        elif high == 0:
            price_text = "Free"
            payment_required = False
        else:
            price_text = f"${low:g}" if low == high else f"${low:g}-${high:g}"
            payment_required = True

        description = clean_text(item.get("description")) or clean_text(item.get("summary")) or None
        event = Event(
            title=title,
            raw_title=title,
            start_datetime=start,
            end_datetime=_local_naive(item.get("end_time")),
            location=location,
            source_url=clean_text(item.get("source_broadcast_url")) or source_url,
            source_name=source_name,
            category=category,
            description=description,
            source_event_id=clean_text(str(item.get("source_id_s") or item.get("source_id") or "")) or None,
            interest_flags=["florida_weekly", *(f"via_{s}" for s in upstream)],
            price_text=price_text,
            price_amount_min=low,
            price_amount_max=high,
            price_currency="USD" if low is not None else None,
            payment_required=payment_required,
        )
        event.apply_access_metadata(overwrite_unknown=True)
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Cape Coral Breeze — event announcements and community-calendar roundups
# ---------------------------------------------------------------------------
#
# Added 2026-10-17 (Luis: "add the cape coral breeze as well for events and
# news stories"). The Breeze has no calendar feed; it prints events as
# community-news articles in a steady house style ("from 4 to 7 p.m.
# Wednesday, Oct. 21, at Four Freedoms Park ... Four Freedoms Park is at 4818
# Tarpon Court, Cape Coral."), either one event per article or a roundup of
# items under bold headings ("Community Calendar | May 1", "This week at The
# Buck"). The adapter reads the category RSS feeds for article links and then
# each article's text.
#
# It only takes what the text states. An occurrence needs an explicit month
# and day; a weekday on its own ("open house Monday") or a recurrence ("every
# Thursday in May") yields nothing rather than a guessed date. A paragraph
# after the first dated one counts as another occurrence only when it also
# names a time, so a registration deadline is not mistaken for the event.

_BREEZE_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
BREEZE_DATE_RE = re.compile(
    r"\b(Jan(?:uary|\.)?|Feb(?:ruary|\.)?|March|Mar\.|April|Apr\.|May|June|July|Aug(?:ust|\.)?|"
    r"Sept(?:ember|\.)?|Sep\.|Oct(?:ober|\.)?|Nov(?:ember|\.)?|Dec(?:ember|\.)?)\s+(\d{1,2})(?:st|nd|rd|th)?\b"
    r"(?:,?\s+(\d{4}))?"
)
_MERIDIEM = r"(a\.m\.|p\.m\.|am\b|pm\b)"
BREEZE_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*" + _MERIDIEM + r"?\s*(?:to|until|-|–|—)\s*(\d{1,2})(?::(\d{2}))?\s*" + _MERIDIEM,
    re.I,
)
BREEZE_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*" + _MERIDIEM, re.I)
# "<Venue> is at <street number> <Street>, <City>." The address must open with
# a street number and a capitalised word, so "The plunge is at 10 a.m." is not
# read as a venue line.
BREEZE_IS_AT_RE = re.compile(
    r"^(?P<venue>[A-Z][^.]{2,90}?)\s+is\s+(?:located\s+)?at\s+(?P<addr>\d+\s+(?:[NSEW]\.?[NSEW]?\.?\s+)?[A-Z0-9].*?)\.?$"
)
# A place named after the date, up to the end of that sentence. A sentence
# ends at a period followed by a capitalised word or the end of the text, so
# "1401 S.E. 47th St., Cape Coral." stays whole; a period after a single
# capital or a street abbreviation ("2691 N.E. Pine Island Road", "Blvd. S.")
# does not end it.
_ABBREV_LOOKBEHIND = (
    r"(?<!\b[A-Z])(?<!\bSt)(?<!\bAve)(?<!\bBlvd)(?<!\bRd)(?<!\bDr)(?<!\bCt)(?<!\bPkwy)(?<!\bLn)(?<!\bFt)(?<!\bMt)"
)
BREEZE_AT_PLACE_RE = re.compile(
    r"\bat\s+(?:the\s+)?(?P<place>(?:[A-Z]|\d+\s+[A-Z])(?:(?!" + _ABBREV_LOOKBEHIND + r"\.(?:\s+[A-Z][a-z]|\s*$))[^;])*)"
)
BREEZE_WEEKDAY_START_RE = re.compile(r"^(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b")
BREEZE_CAPTION_RE = re.compile(r"\bPHOTOS?\b|\bPHOTO PROVIDED\b")
BREEZE_SEPARATOR_RE = re.compile(r"^[\s\-–—*•_]+$")
BREEZE_ZOOM_RE = re.compile(r"\b(?:via|on|over)\s+Zoom\b", re.I)
BREEZE_MAX_DAYS_AHEAD = 200
# A month/day earlier in the year than the article is read as next year only
# when that lands soon after publication: a December article about a January
# event, not a past date ("closed on March 3") pushed a year out.
BREEZE_MAX_ROLLOVER_DAYS = 100


def _hour24(hour: str, minute: str | None, meridiem: str | None) -> tuple[int, int]:
    h = int(hour) % 12
    if meridiem and meridiem.lower().startswith("p"):
        h += 12
    return h, int(minute or 0)


def _breeze_times(text: str) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    match = BREEZE_TIME_RANGE_RE.search(text)
    if match:
        end_mer = match.group(6)
        start_mer = match.group(3) or end_mer
        start = _hour24(match.group(1), match.group(2), start_mer)
        end = _hour24(match.group(4), match.group(5), end_mer)
        if not match.group(3) and start > end:
            start = _hour24(match.group(1), match.group(2), "a.m.")
        return start, end
    if re.search(r"\bnoon\b", text, re.I) and not BREEZE_TIME_RE.search(text):
        return (12, 0), None
    match = BREEZE_TIME_RE.search(text)
    if match:
        return _hour24(match.group(1), match.group(2), match.group(3)), None
    return None, None


def _breeze_date_match(text: str, published: date) -> tuple[date, int] | None:
    """The first month/day in `text` as an upcoming date, and where it ends."""
    match = BREEZE_DATE_RE.search(text)
    if not match:
        return None
    month = _BREEZE_MONTHS[match.group(1)[:3].lower()]
    day = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else published.year
    try:
        found = date(year, month, day)
    except ValueError:
        return None
    if not match.group(3) and found < published - timedelta(days=60):
        try:
            found = date(year + 1, month, day)
        except ValueError:
            return None
        if found > published + timedelta(days=BREEZE_MAX_ROLLOVER_DAYS):
            return None
    if found < published or found > published + timedelta(days=BREEZE_MAX_DAYS_AHEAD):
        return None
    return found, match.end()


def _breeze_is_at(paragraph: str) -> str | None:
    match = BREEZE_IS_AT_RE.match(paragraph)
    if not match or "," not in match.group("addr"):
        return None
    venue = re.sub(r"^The\s+", "", match.group("venue").strip())
    return f"{venue}, {match.group('addr').strip()}"


def _breeze_at_place(paragraph: str) -> str | None:
    for match in BREEZE_AT_PLACE_RE.finditer(paragraph):
        place = match.group("place").strip().rstrip(",.").strip()
        if 3 <= len(place) <= 120:
            return place
    return None


def _same_place(place: str, venue_line: str) -> bool:
    """Whether an "at <place>" mention and an "<X> is at <address>" line name one venue."""
    name = venue_line.split(",", 1)[0].strip().lower()
    low = place.lower()
    return bool(name) and (name in low or low.split(",", 1)[0].strip() in name)


def _breeze_paragraphs(soup: BeautifulSoup) -> list[tuple[str, bool]]:
    """(text, is_bold_line) for each non-empty paragraph of the article body."""
    body = soup.find(id="article_content_wrap") or soup.find("article") or soup
    out: list[tuple[str, bool]] = []
    for p in body.find_all("p"):
        text = clean_text(p.get_text(" "))
        if not text or text.startswith("Copyright ©"):
            continue
        strong = p.find(["strong", "b"])
        bold = bool(strong) and clean_text(strong.get_text(" ")) == text
        out.append((text, bold))
    return out


def _breeze_is_heading(text: str, bold: bool) -> bool:
    return (
        bold
        and 4 <= len(text) <= 160
        and not text[0].isdigit()
        and not BREEZE_WEEKDAY_START_RE.match(text)
        and not BREEZE_DATE_RE.match(text)
        and "Admission" not in text
    )


def parse_breeze_feed(xml: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(xml, "xml")
    items: list[dict[str, Any]] = []
    for item in soup.find_all("item"):
        link = clean_text(item.link.get_text() if item.link else "")
        if not link:
            continue
        published = None
        if item.pubDate:
            try:
                published = date_parser.parse(item.pubDate.get_text()).date()
            except (ValueError, OverflowError):
                published = None
        items.append({
            "title": clean_text(item.title.get_text() if item.title else ""),
            "link": link,
            "published": published,
        })
    return items


def parse_breeze_article(
    html: str,
    url: str,
    source_name: str,
    published: date | None = None,
) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    headline = clean_text(h1.get_text(" ")) if h1 else ""
    if published is None:
        meta = soup.find(id="single_meta")
        stamp = meta.find("time") if meta else None
        if stamp is not None:
            try:
                published = date_parser.parse(stamp.get_text()).date()
            except (ValueError, OverflowError):
                published = None
    if published is None:
        return []

    paragraphs = [
        (text, bold) for text, bold in _breeze_paragraphs(soup)
        if not BREEZE_SEPARATOR_RE.match(text) and not BREEZE_CAPTION_RE.search(text)
    ]

    # Article-wide venue: an "X is at <address>." line, or a bold name line
    # followed by a bold address line (the venue footer of a schedule).
    article_venue = None
    for text, _bold in paragraphs:
        article_venue = article_venue or _breeze_is_at(text)
    if article_venue is None:
        for (name, name_bold), (addr, addr_bold) in zip(paragraphs, paragraphs[1:]):
            if name_bold and addr_bold and not name[0].isdigit() and addr[0].isdigit() and "," in addr:
                article_venue = f"{name}, {addr}"
                break

    heads = [i for i, (text, bold) in enumerate(paragraphs) if _breeze_is_heading(text, bold)]
    if len(heads) >= 2:
        # A roundup: each bold heading opens an item; text before the first
        # heading is the article's own introduction and is not an event.
        bounds = list(zip(heads, heads[1:] + [len(paragraphs)]))
        items = [(paragraphs[a][0], [t for t, _b in paragraphs[a + 1 : b]]) for a, b in bounds]
    else:
        items = [(headline, [t for t, _b in paragraphs])]

    slug = url.rstrip("/").rsplit("/", 1)[-1]
    events: list[Event] = []
    for index, (title, texts) in enumerate(items):
        if not title or not texts:
            continue
        item_text = " ".join(texts)
        venue_line = None
        for text in texts:
            venue_line = venue_line or _breeze_is_at(text)

        occurrences: list[tuple[date, tuple[int, int] | None, tuple[int, int] | None, str | None]] = []
        seen: set[date] = set()
        for position, text in enumerate(texts):
            dated = _breeze_date_match(text, published)
            if dated is None or dated[0] in seen:
                continue
            day, date_end = dated
            start, end = _breeze_times(text)
            if occurrences and start is None:
                continue
            if start is None:
                start, end = _breeze_times(" ".join(texts[position + 1 :]))
            seen.add(day)
            occurrences.append((day, start, end, _breeze_at_place(text[date_end:])))
        if not occurrences:
            continue

        # Where each occurrence happens: the place its own line names (or the
        # item's "X is at <address>" line when that is the same place, being
        # fuller); else the item's venue line; else the first place any
        # occurrence named; else Zoom; else the article's venue footer.
        first_place = next((occ[3] for occ in occurrences if occ[3]), None)
        fallback = venue_line or first_place
        if fallback is None and BREEZE_ZOOM_RE.search(item_text):
            fallback = "Online (Zoom)"
        fallback = fallback or article_venue

        for day, start, end, place in occurrences:
            if place and venue_line:
                location = venue_line if _same_place(place, venue_line) else place
            else:
                location = place or fallback
            start_dt = datetime(day.year, day.month, day.day, *(start or (0, 0)))
            end_dt = datetime(day.year, day.month, day.day, *end) if end else None
            if end_dt and end_dt < start_dt:
                end_dt += timedelta(days=1)
            event = Event(
                title=title,
                raw_title=title,
                start_datetime=start_dt.isoformat(timespec="seconds"),
                end_datetime=end_dt.isoformat(timespec="seconds") if end_dt else None,
                location=location,
                source_url=url,
                source_name=source_name,
                category="Community listing",
                description=item_text[:900] or None,
                source_event_id=f"{slug}#{index}",
                interest_flags=["cape_coral_breeze"],
            )
            event.apply_access_metadata(overwrite_unknown=True)
            events.append(event)
    return events


# ---------------------------------------------------------------------------
# Florida Weekly — "What to do, where to go", the weekly column
# ---------------------------------------------------------------------------
#
# Added 2026-10-18. Luis: "I want that article read. those are curated events
# from a person. worth rating higher." The column is published each Tuesday
# by Florida Weekly staff and covers Wednesday to Tuesday: a few Top Picks
# ("10/16 - Title – ..."), then one heading per day ("WEDNESDAY 10.14" or, in
# older weeks, "WEDNESDAY 9/30"), then ONGOING. Every listing is one paragraph
# in a fixed house style:
#
#   <Title> – <Kind> at <Venue> at <time>. <Description>. Tickets start at
#   $<n>. <street address>, <City>. <phone> or <website> .
#
# The column's section page (fort-myers/arts-entertainment/what-to-do-where-
# to-go/) links the newest column under the headline "What to do, where to
# go"; the article's own title changes every week, so the index is read by
# that headline, not by URL.
#
# As with the Breeze, only what the text states is kept. A listing under a
# day heading takes that date; with no time it stays a bare date. An ONGOING
# listing yields a row per stated range ("available Oct. 16-18 & Oct. 23-25")
# and nothing for a recurrence ("every Sunday") or a run with only an end
# ("through Oct. 25"). A Top Pick tags the listing it matches; one that
# matches no row stands on its own date. Photo captions have no " – " and
# are skipped.

FW_COLUMN_HEADLINE_RE = re.compile(r"^\s*what to do,?\s+where to go\s*$", re.I)
_FW_DAY_RE = re.compile(r"^(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY\s+(\d{1,2})\s*[./]\s*(\d{1,2})$", re.I)
_FW_PICK_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\s*-\s*(.+)$")
_FW_TITLE_SEP_RE = re.compile(r"\s+[–—]\s+")
_FW_TIME = r"\d{1,2}(?::\d{2})?\s*[ap]\.m\.?"
_FW_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.m\.?")
_FW_AT_TIME_RE = re.compile(
    r"^(?P<lead>.*?)(?:^|\s)(?:[Aa]t|in)\s+(?P<venue>.+?),?\s+at\s+(?P<t1>" + _FW_TIME + r")"
)
_FW_AT_PLACE_RE = re.compile(
    r"^(?P<lead>.*?)(?:^|\s)(?:[Aa]t|in)\s+(?P<venue>.+?)"
    r"(?=\s+(?:with|available|every|through|on display|from)\b"
    r"|\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d|,\s|$)"
)
# A sentence ends at a period before a capital, except after a single
# capital ("U. Tobe Recital Hall"), a street or month abbreviation.
_FW_SENTENCE_END_RE = re.compile(
    r"(?<!\b[A-Z])(?<!\bSt)(?<!\bMt)(?<!\bFt)(?<!\bDr)(?<!\bAve)(?<!\bBlvd)(?<!\bRd)(?<!\bBldg)"
    r"(?<!\bJan)(?<!\bFeb)(?<!\bMar)(?<!\bApr)(?<!\bAug)(?<!\bSep)(?<!\bSept)(?<!\bOct)(?<!\bNov)(?<!\bDec)"
    r"\.\s+(?=[A-Z“\"])"
)
_FW_MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_FW_RANGE_RE = re.compile(
    r"\b" + _FW_MONTH + r"\s+(\d{1,2})\s*[-–]\s*(?:" + _FW_MONTH + r"\s+)?(\d{1,2})\b(?:,?\s+(\d{4}))?"
)
_FW_CITY_RE = re.compile(
    r",\s*(?P<city>Fort Myers Beach|North Fort Myers|Fort Myers|Cape Coral|Bonita Springs|Estero|Sanibel|"
    r"Captiva|Naples|Marco Island|Punta Gorda|Port Charlotte|Lehigh Acres|Pine Island|Matlacha|Bokeelia|"
    r"St\. James City|Alva|Immokalee|LaBelle|Labelle|Englewood|Boca Grande|Babcock Ranch)\s*\.(?=\s|$)"
)
_FW_PRICE_RE = re.compile(
    r"\b(?:Tickets|Registration|Admission|Entry)\s+(?P<verb>starts?\s+at|are|is|from)\s+\$(?P<amount>\d[\d,]*(?:\.\d+)?)",
    re.I,
)
_FW_FREE_RE = re.compile(r"\b(?:Tickets|Admission|Entry)\s+(?:are|is)\s+free\b|\bfree[- ]to[- ]attend\b|\bfree admission\b", re.I)


def _fw_norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _fw_date(month: int, day: int, published: date) -> date | None:
    try:
        found = date(published.year, month, day)
    except ValueError:
        return None
    if found < published - timedelta(days=120):
        try:
            found = date(published.year + 1, month, day)
        except ValueError:
            return None
    return found


def _fw_split_head(text: str) -> tuple[str, str]:
    """The listing's first sentence (kind, venue, time) and the rest."""
    match = _FW_SENTENCE_END_RE.search(text)
    if not match:
        return text.rstrip(" ."), ""
    return text[: match.start()].strip(), text[match.end():].strip()


def _fw_address(rest: str) -> tuple[str | None, str | None, str]:
    """(street address, city, description) from what follows the first sentence."""
    matches = list(_FW_CITY_RE.finditer(rest))
    if not matches:
        return None, None, rest.strip()
    city = matches[-1]
    segment = rest[: city.start()]
    numbered = [m.end() for m in re.finditer(r"(?:^|[.!?]\s+)(?=\d)", segment)]
    if numbered:
        start = numbered[-1]
    else:
        sentences = [m.end() for m in _FW_SENTENCE_END_RE.finditer(segment)]
        start = sentences[-1] if sentences else 0
    address = segment[start:].strip().rstrip(",")
    if not address or len(address) > 120:
        return None, city.group("city"), segment.strip()
    return address, city.group("city"), segment[:start].strip()


def _fw_price(text: str, lead: str) -> tuple[str | None, float | None, float | None, bool | None]:
    match = _FW_PRICE_RE.search(text)
    if match:
        amount = float(match.group("amount").replace(",", ""))
        if match.group("verb").lower() in {"are", "is"}:
            return f"${amount:g}", amount, amount, True
        return f"From ${amount:g}", amount, None, True
    if _FW_FREE_RE.search(text) or lead.lower().startswith("free "):
        return "Free", 0.0, 0.0, False
    return None, None, None, None


def parse_fw_column_index(html: str, base_url: str) -> list[str]:
    """Column article URLs on the section page, newest first, as linked."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select('a[href*="/article_"]'):
        if not FW_COLUMN_HEADLINE_RE.match(clean_text(anchor.get_text(" "))):
            continue
        url = urljoin(base_url, str(anchor.get("href") or "").split("#", 1)[0])
        if url not in links:
            links.append(url)
    return links


def _fw_blocks(soup: BeautifulSoup) -> list[str]:
    body = soup.select_one("#article-body") or soup.find("article") or soup
    texts: list[str] = []
    for el in body.find_all(["h2", "h3", "h4", "p", "li"]):
        if el.name == "p" and el.find_parent("li") is not None:
            continue  # the same text as its list item
        text = clean_text(el.get_text(" "))
        if text and (not texts or texts[-1] != text):
            texts.append(text)
    return texts


def parse_fw_column_article(html: str, url: str, source_name: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    stamp = soup.select_one("time[datetime]")
    try:
        published = date_parser.parse(str(stamp.get("datetime"))).date() if stamp else None
    except (ValueError, OverflowError):
        published = None
    if published is None:
        return []
    key_match = re.search(r"article_([0-9a-f-]+)\.html", url)
    article_key = key_match.group(1) if key_match else url

    def build(title: str, head: str, rest: str, start: str, end: str | None, venue: str, lead: str) -> Event:
        venue = re.sub(r"^the\s+", "", venue.strip().rstrip(","))
        address, city, description = _fw_address(rest)
        parts = [venue]
        if address and address.lower() not in venue.lower():
            parts.append(address)
        # The city closes the address; with no street address it is added only
        # when the venue does not already end with it.
        if city and (len(parts) > 1 or not venue.lower().endswith(city.lower())):
            parts.append(city)
        price_text, low, high, paid = _fw_price(" ".join((head, description)), lead)
        event = Event(
            title=title,
            raw_title=title,
            start_datetime=start,
            end_datetime=end,
            location=", ".join(p for p in parts if p) or None,
            source_url=url,
            source_name=source_name,
            category=(lead[:1].upper() + lead[1:]) if lead else None,
            description=(description or head)[:900] or None,
            source_event_id=f"{article_key}:{_fw_norm(title).replace(' ', '-')}:{start[:10]}",
            interest_flags=["florida_weekly", "fw_column"],
            price_text=price_text,
            price_amount_min=low,
            price_amount_max=high,
            price_currency="USD" if low is not None else None,
            payment_required=paid,
        )
        event.apply_access_metadata(overwrite_unknown=True)
        # "Tickets start at $76" states a floor, not a ceiling; the generic
        # inference above would copy the floor into the maximum.
        if low is not None:
            event.price_amount_min, event.price_amount_max = low, high
        return event

    def dated(title: str, text: str, day: date) -> Event | None:
        head, rest = _fw_split_head(text)
        timed = _FW_AT_TIME_RE.match(head)
        if timed and len(timed.group("venue")) <= 100:
            tm = _FW_TIME_RE.match(timed.group("t1"))
            assert tm is not None
            hour, minute = _hour24(tm.group(1), tm.group(2), tm.group(3))
            start = f"{day.isoformat()}T{hour:02d}:{minute:02d}:00"
            return build(title, head, rest, start, None, timed.group("venue"), timed.group("lead").strip())
        placed = _FW_AT_PLACE_RE.match(head)
        if placed and len(placed.group("venue")) <= 100:
            return build(title, head, rest, day.isoformat(), None, placed.group("venue"), placed.group("lead").strip())
        return None

    def ongoing(title: str, text: str) -> list[Event]:
        head, rest = _fw_split_head(text)
        if re.search(r"\bevery\b", head, re.I):
            return []
        placed = _FW_AT_PLACE_RE.match(head)
        if not placed or len(placed.group("venue")) > 100:
            return []
        out: list[Event] = []
        for rng in _FW_RANGE_RE.finditer(head):
            m1 = _BREEZE_MONTHS[rng.group(1)[:3].lower()]
            m2 = _BREEZE_MONTHS[(rng.group(3) or rng.group(1))[:3].lower()]
            first = _fw_date(m1, int(rng.group(2)), published)
            if first is None:
                continue
            try:
                last = date(int(rng.group(5)) if rng.group(5) else first.year, m2, int(rng.group(4)))
            except ValueError:
                continue
            if last < first:
                try:
                    last = date(last.year + 1, last.month, last.day)
                except ValueError:
                    continue
            out.append(build(title, head, rest, first.isoformat(), last.isoformat(), placed.group("venue"),
                             placed.group("lead").strip()))
        return out

    events: list[Event] = []
    picks: list[tuple[str, str, date]] = []
    section = "preamble"
    day: date | None = None
    for text in _fw_blocks(soup):
        heading = _FW_DAY_RE.match(text)
        if heading:
            section, day = "day", _fw_date(int(heading.group(1)), int(heading.group(2)), published)
            continue
        upper = text.upper()
        if upper == "ONGOING":
            section, day = "ongoing", None
            continue
        if upper == "TOP PICKS":
            section = "picks"
            continue
        pick = _FW_PICK_RE.match(text)
        if pick and section in {"preamble", "picks"}:
            split = _FW_TITLE_SEP_RE.split(pick.group(3), maxsplit=1)
            on = _fw_date(int(pick.group(1)), int(pick.group(2)), published)
            if len(split) == 2 and on is not None:
                picks.append((split[0].strip(), split[1].strip(), on))
            continue
        split = _FW_TITLE_SEP_RE.split(text, maxsplit=1)
        if len(split) != 2 or not split[0].strip() or len(split[0]) > 160:
            continue  # a photo caption or a stray line
        title, body = split[0].strip(), split[1].strip()
        if section == "day" and day is not None:
            event = dated(title, body, day)
            if event is not None:
                events.append(event)
        elif section == "ongoing":
            events.extend(ongoing(title, body))

    for title, body, on in picks:
        matching = [e for e in events if _fw_norm(e.title) == _fw_norm(title)]
        if not matching:
            event = dated(title, body, on)
            matching = [event] if event is not None else []
            events.extend(matching)
        for event in matching:
            if "fw_top_pick" not in event.interest_flags:
                event.interest_flags.append("fw_top_pick")

    unique: list[Event] = []
    seen: set[tuple[str, str]] = set()
    for event in events:
        key = (_fw_norm(event.title), event.start_datetime)
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return unique
