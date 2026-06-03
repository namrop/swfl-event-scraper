from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any


PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
FREE_RE = re.compile(r"\bfree\b|\bno\s+cost\b", flags=re.I)
DROP_IN_RE = re.compile(r"\bdrop[-\s]?in\b|\bwalk[-\s]?in\b|\bopen\s+(?:play|pickleball|gym)\b|\bno\s+registration\s+required\b", flags=re.I)
REGISTRATION_RE = re.compile(r"\bregistration\s+required\b|\bregister\b|\bsign\s*up\b|\benroll\b", flags=re.I)
SERIES_CLASS_RE = re.compile(
    r"\b(?:yoga|tai\s*chi|line\s*dance|dance|pottery|glass|stained\s+glass|bead|beadmaking|raku|wheel\s+throwing|silver\s+rings|polymer\s+clay|hula|circuit\s+training|cardio|camp\w*)\b",
    flags=re.I,
)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()


def infer_access_metadata(
    title: str,
    description: str | None = None,
    category: str | None = None,
    source_name: str | None = None,
) -> dict[str, Any]:
    """Infer price/registration metadata from visible event text.

    The scraper should preserve unknowns instead of pretending every parks class
    is drop-in. These fields are conservative triage hints for shortlist/ranking:
    structured sources can override them later when detail pages expose exact
    fees, enrollment state, or seasonal registration windows.
    """
    text = " ".join(part for part in [title, description, category, source_name] if part)
    amounts = [float(match) for match in PRICE_RE.findall(text)]
    has_free = bool(FREE_RE.search(text))
    has_drop_in = bool(DROP_IN_RE.search(text))
    no_registration_required = bool(re.search(r"\bno\s+registration\s+required\b", text, flags=re.I))
    has_registration = bool(REGISTRATION_RE.search(text)) and not no_registration_required
    looks_like_class_series = bool(SERIES_CLASS_RE.search(text))

    if amounts:
        low = min(amounts)
        high = max(amounts)
        price_text = f"${low:g}" if low == high else f"${low:g}-${high:g}"
        payment_required: bool | None = True
        price_currency = "USD"
    elif has_free:
        low = high = None
        price_text = "Free"
        payment_required = False
        price_currency = "USD"
    else:
        low = high = None
        price_text = None
        payment_required = None
        price_currency = None

    if has_drop_in and not has_registration:
        registration_required: bool | None = False
        access_type = "drop_in"
        joinability = "drop_in_ok"
    elif has_registration:
        registration_required = True
        access_type = "registration_required"
        joinability = "registration_needed"
    elif looks_like_class_series:
        registration_required = None
        access_type = "class_series"
        joinability = "verify_mid_session_joinability"
    else:
        registration_required = None
        access_type = "unknown"
        joinability = "unknown"

    if has_free and has_drop_in and not has_registration:
        payment_required = False

    return {
        "price_text": price_text,
        "price_amount_min": low,
        "price_amount_max": high,
        "price_currency": price_currency,
        "payment_required": payment_required,
        "registration_required": registration_required,
        "access_type": access_type,
        "joinability": joinability,
    }


@dataclass(slots=True)
class Event:
    title: str
    start_datetime: str
    source_url: str
    source_name: str = ""
    end_datetime: str | None = None
    location: str | None = None
    category: str | None = None
    description: str | None = None
    raw_title: str | None = None
    source_event_id: str | None = None
    interest_flags: list[str] = field(default_factory=list)
    is_spam: bool = False
    price_text: str | None = None
    price_amount_min: float | None = None
    price_amount_max: float | None = None
    price_currency: str | None = None
    payment_required: bool | None = None
    registration_required: bool | None = None
    access_type: str | None = None
    joinability: str | None = None

    def __post_init__(self) -> None:
        metadata = infer_access_metadata(self.title, self.description, self.category, self.source_name)
        for key, value in metadata.items():
            if getattr(self, key) is None and value is not None:
                setattr(self, key, value)

    @property
    def id(self) -> str:
        basis = "|".join(
            [
                normalize_title(self.title),
                self.start_datetime[:10],
                (self.location or "").lower().strip(),
                self.source_event_id or "",
            ]
        )
        return sha256(basis.encode("utf-8")).hexdigest()[:24]

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "start_datetime": self.start_datetime,
            "end_datetime": self.end_datetime,
            "location": self.location,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "category": self.category,
            "description": self.description,
            "raw_title": self.raw_title or self.title,
            "source_event_id": self.source_event_id,
            "interest_flags": json.dumps(self.interest_flags),
            "is_spam": int(self.is_spam),
            "price_text": self.price_text,
            "price_amount_min": self.price_amount_min,
            "price_amount_max": self.price_amount_max,
            "price_currency": self.price_currency,
            "payment_required": None if self.payment_required is None else int(self.payment_required),
            "registration_required": None if self.registration_required is None else int(self.registration_required),
            "access_type": self.access_type,
            "joinability": self.joinability,
        }
