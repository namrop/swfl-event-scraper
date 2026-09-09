"""Turning a scraped event (or a migrated SQLite row) into a ledger candidate.

One function per input shape, one shared normaliser, so a row migrated from
the retired Acubens database and a row scraped on Sol this morning are the
same object apart from their provenance.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .geo import Place, locate
from .interest import rate
from .ledger import LEDGER_SCHEMA, candidate_id

# Three migrated rows carried a U+FEFF byte-order mark inside their text, which
# is legal JSON and illegal to `cue vet`. Strip BOMs and C0 control characters
# (keeping nothing but the text) at the point rows are built, so the ledger
# never records a character its own contract cannot read.
_JUNK = re.compile(r"[\ufeff\ufffe\u200b\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


_MINUTE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}$")


def norm_stamp(value):
    """Normalise a start/end stamp to `YYYY-MM-DDTHH:MM:SS` or a bare date.

    Sources disagree: the Tribe API gives seconds, the Lee County and WebTrac
    adapters give minutes, several civic feeds give a date with no time at all.
    Padding the minute-precision ones to `:00` makes the ledger uniform without
    inventing information — a date with no time stays a date, which the
    contract models explicitly so the newsroom can tell the two apart.
    """
    if not isinstance(value, str):
        return value
    v = value.strip().replace(" ", "T", 1)
    if not v:
        return None
    if _MINUTE_ONLY.match(value.strip()):
        v += ":00"
    return v


def scrub(value):
    if not isinstance(value, str):
        return value
    cleaned = _JUNK.sub("", value).strip()
    return cleaned or None


MEMBERS_RE = re.compile(r"\bmembers?[- ]only|resident member|membership required\b", re.I)
TICKET_RE = re.compile(r"\bticket|admission|box office|purchase\b", re.I)

ACCESS_MAP = {
    "drop_in": "drop_in",
    "public_meeting": "public_meeting",
    "registration_required": "registration",
    "class_series": "registration",
    "listed_event_no_registration": "drop_in",
    "unknown": "unknown",
    None: "unknown",
}


def _access(access_type: str | None, payment_required: Any, price_min: Any, text: str) -> str:
    if MEMBERS_RE.search(text):
        return "members"
    mapped = ACCESS_MAP.get(access_type, "unknown")
    if mapped in {"unknown", "drop_in"}:
        paid = bool(payment_required) or (price_min not in (None, "") and float(price_min or 0) > 0)
        if paid and TICKET_RE.search(text):
            return "ticketed"
    return mapped


def _tags(raw: Any) -> list[str]:
    """The old scraper's `interest_flags` were source tags, not preferences.

    They are kept verbatim under `source_tags` so the migration loses nothing;
    the semantic vocabulary lives in `interest_tags`.
    """
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return [str(raw)]
    return [str(x) for x in parsed] if isinstance(parsed, list) else [str(parsed)]


def build_candidate(
    *,
    title: str,
    start: str | None,
    end: str | None,
    venue: str | None,
    source_name: str,
    source_url: str,
    category: str | None,
    description: str | None,
    source_event_id: str | None,
    source_row_id: str | None,
    source_tags: list[str],
    price_text: str | None,
    price_min: float | None,
    price_max: float | None,
    price_currency: str | None,
    payment_required: Any,
    registration_required: Any,
    access_type: str | None,
    joinability: str | None,
    is_spam: Any,
    source_default: Place | None,
    source_noisy: bool = False,
) -> dict[str, Any]:
    title = scrub(title) or "(untitled)"
    venue = scrub(venue)
    category = scrub(category)
    description = scrub(description)
    geo = locate(venue, source_default=source_default)
    text = " ".join(p for p in (title, description, category, venue) if p)
    access = _access(access_type, payment_required, price_min, text)

    r = rate(
        title=title,
        description=description,
        category=category,
        venue=venue,
        source_name=source_name,
        distance_mi=geo["distance_mi"],
        geo_precision=geo["geo_precision"],
        access=access_type,
        price_min=price_min,
        price_text=price_text,
    )

    return {
        "ledger_schema": LEDGER_SCHEMA,
        "id": candidate_id(title, start, venue),
        "title": title,
        "start": norm_stamp(start),
        "end": norm_stamp(end),
        "venue": venue,
        "address": venue,  # the sources give one free-text place string; kept split so a
                           # future adapter with a real postal address has a field to fill
        "city": geo["city"],
        "county": geo["county"],
        "region": geo["region"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "distance_mi": geo["distance_mi"],
        "geo_precision": geo["geo_precision"],
        "source_name": source_name,
        "source_url": source_url,
        "source_event_id": source_event_id,
        "source_row_id": source_row_id,
        "source_tags": source_tags,
        "source_noisy": source_noisy,
        "category": category,
        "description": description,
        "interest_tags": r.interest_tags,
        "interest_costs": r.costs,
        "audience": r.audience,
        "cost": {
            "price_text": price_text,
            "price_min": price_min,
            "price_max": price_max,
            "currency": price_currency,
        },
        "access": access,
        "registration_required": None if registration_required is None else bool(registration_required),
        "joinability": joinability,
        "is_spam": bool(is_spam),
        "rating": r.rating,
        "rating_reason": r.rating_reason,
        "feedback": None,
        "feedback_note": None,
        "feedback_at": None,
        "status": "candidate",
    }


def candidate_from_event(event, source) -> dict[str, Any]:
    return build_candidate(
        title=event.title,
        start=event.start_datetime,
        end=event.end_datetime,
        venue=event.location,
        source_name=event.source_name or source.name,
        source_url=event.source_url,
        category=event.category,
        description=event.description,
        source_event_id=event.source_event_id,
        source_row_id=event.id,
        source_tags=list(event.interest_flags or []),
        price_text=event.price_text,
        price_min=event.price_amount_min,
        price_max=event.price_amount_max,
        price_currency=event.price_currency,
        payment_required=event.payment_required,
        registration_required=event.registration_required,
        access_type=event.access_type,
        joinability=event.joinability,
        is_spam=event.is_spam,
        source_default=source.default_place(),
        source_noisy=(source.kind.value == "ticketed"),
    )


def candidate_from_sqlite_row(row: dict[str, Any], source_defaults: dict[str, Place]) -> dict[str, Any]:
    return build_candidate(
        title=row["title"],
        start=row["start_datetime"],
        end=row.get("end_datetime"),
        venue=row.get("location"),
        source_name=row["source_name"],
        source_url=row["source_url"],
        category=row.get("category"),
        description=row.get("description"),
        source_event_id=row.get("source_event_id"),
        source_row_id=row.get("id"),
        source_tags=_tags(row.get("interest_flags")),
        price_text=row.get("price_text"),
        price_min=row.get("price_amount_min"),
        price_max=row.get("price_amount_max"),
        price_currency=row.get("price_currency"),
        payment_required=row.get("payment_required"),
        registration_required=row.get("registration_required"),
        access_type=row.get("access_type"),
        joinability=row.get("joinability"),
        is_spam=row.get("is_spam"),
        source_default=source_defaults.get(row["source_name"]),
    )
