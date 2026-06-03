from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable
from urllib.parse import quote

import requests
import urllib3

from .models import Event
from .parsers import (
    enrich_event_from_civicengage_detail,
    parse_capecoral_revize_events,
    parse_capecoral_webtrac_reader_markdown,
    parse_fort_myers_civicengage_events,
    parse_generic_jsonld_events,
    parse_leegov_parks_events,
    parse_librarymarket_events,
    parse_metrolagoons_events_html,
    parse_tribe_events_payload,
)
from .sources import Source

USER_AGENT = "swfl-event-scraper/0.1 (+local civic calendar appliance)"


def capecoral_revize_data_url(public_url: str) -> str:
    return (
        "https://www.capecoral.gov/_assets_/plugins/revizeCalendar/calendar_data_handler.php"
        "?webspace=capecoralfl&relative_revize_url=//cms6.revize.com&protocol=https:"
    )


def capecoral_webtrac_reader_url(public_url: str) -> str:
    return "https://r.jina.ai/http://flcapecoralweb.myvscloud.com/webtrac/web/search.html?display=Calendar&module=Event"


def fetch_text(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def fetch_json_lenient(url: str) -> dict[str, object]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.8,*/*;q=0.5"},
            timeout=30,
        )
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.8,*/*;q=0.5"},
            timeout=30,
            verify=False,
        )
    response.raise_for_status()
    return response.json()


def fetch_tribe_events(source_url: str) -> dict[str, object]:
    now = datetime.now()
    api_url = (
        f"{source_url.rstrip('/')}/wp-json/tribe/events/v1/events"
        f"?per_page=50&start_date={now.date().isoformat()}&end_date={now.year + 1}-12-31"
    )
    events: list[dict[str, object]] = []
    next_url: str | None = api_url
    total = 0
    total_pages = 0
    while next_url:
        payload = fetch_json_lenient(next_url)
        events.extend(payload.get("events", []))
        total = int(payload.get("total") or len(events))
        total_pages = int(payload.get("total_pages") or total_pages or 1)
        next_url = payload.get("next_rest_url") if isinstance(payload.get("next_rest_url"), str) else None
    return {"events": events, "total": total, "total_pages": total_pages}


def fetch_metrolagoons_month(month_label: str, lagoon_name: str) -> str:
    url = (
        "https://www.metrolagoons.com/ajax/functions.php"
        f"?operation=eventsCalendar&month={quote(month_label)}&tag={quote(lagoon_name)}&category="
    )
    payload = fetch_json_lenient(url)
    return str(payload.get("html") or "")


def fetch_brightwater_lagoon_events() -> str:
    now = datetime.now()
    month_label = now.strftime("%b %Y")
    return fetch_metrolagoons_month(month_label, "Brightwater Lagoon")


def fetch_leegov_parks_month(year: int, month: int) -> dict[str, object]:
    url = "https://www.leegov.com/parks/s_events/_layouts/15/LeeCounty.Events/CalendarWS.asmx/getEvents"
    payload = (
        "{ gEvents: {"
        f"Year: {year},"
        f"Month: {month},"
        'filterK : "",filterDF : "",filterSD : "",filterET : "",filterAG : "",issf : ""'
        "} }"
    )
    response = requests.post(
        url,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://www.leegov.com/parks/events",
        },
        timeout=30,
    )
    response.raise_for_status()
    return json.loads(response.json()["d"])


def scrape_source(source: Source) -> tuple[list[Event], str | None]:
    try:
        if source.parser == "capecoral_revize":
            payload = fetch_text(capecoral_revize_data_url(source.url))
            events = parse_capecoral_revize_events(payload, source_url=source.url)
        elif source.parser == "capecoral_webtrac_reader":
            now = datetime.now()
            markdown = fetch_text(capecoral_webtrac_reader_url(source.url))
            if "Target URL returned error 403" in markdown or "Attention Required! | Cloudflare" in markdown:
                return [], "reader fallback reached Cloudflare block"
            events = parse_capecoral_webtrac_reader_markdown(markdown, year=now.year, month=now.month)
        elif source.parser == "librarymarket":
            html = fetch_text(source.url)
            events = parse_librarymarket_events(html, source_url=source.url)
        elif source.parser == "fort_myers_civicengage":
            html = fetch_text(source.url)
            events = parse_fort_myers_civicengage_events(html, source_url=source.url)
            for event in events:
                try:
                    detail_html = fetch_text(event.source_url)
                except Exception:
                    continue
                enrich_event_from_civicengage_detail(event, detail_html)
        elif source.parser == "generic_jsonld":
            html = fetch_text(source.url)
            events = parse_generic_jsonld_events(html, source_url=source.url, source_name=source.name)
        elif source.parser == "leegov_parks":
            now = datetime.now()
            payload = fetch_leegov_parks_month(now.year, now.month)
            events = parse_leegov_parks_events(payload, source_url=source.url)
        elif source.parser == "tribe_events_api":
            payload = fetch_tribe_events(source.url)
            events = parse_tribe_events_payload(payload, source_url=source.url, source_name=source.name)
        elif source.parser == "metrolagoons_brightwater":
            html = fetch_brightwater_lagoon_events()
            events = parse_metrolagoons_events_html(html, source_url=source.url, lagoon_name="Brightwater Lagoon")
        elif source.parser in {"unsupported_webtrac", "static_links", "eventbrite_optional", "civiclive_calendar_pending"}:
            # Source is intentionally tracked in the civic source map, but the v0
            # request-based adapter either needs browser rendering, a discovered
            # private endpoint, or an authenticated/API path before insertion.
            return [], f"adapter pending for {source.parser}"
        else:
            return [], f"unknown parser {source.parser}"
    except Exception as exc:  # noqa: BLE001 - surface per-source health without killing whole scrape.
        return [], f"{type(exc).__name__}: {exc}"

    for event in events:
        if not event.source_name:
            event.source_name = source.name
    return events, None


def scrape_sources(sources: Iterable[Source]) -> tuple[list[Event], list[dict[str, object]]]:
    all_events: list[Event] = []
    health: list[dict[str, object]] = []
    for source in sources:
        events, error = scrape_source(source)
        all_events.extend(events)
        health.append(
            {
                "source": source.name,
                "kind": source.kind.value,
                "url": source.url,
                "events": len(events),
                "status": "ok" if error is None else "pending" if error.startswith("adapter pending") else "error",
                "message": error,
            }
        )
    return all_events, health
