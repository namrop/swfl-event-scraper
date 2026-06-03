from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any


PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
PRICE_CONTEXT_RE = re.compile(
    r"\b(?:fee|cost|admission|ticket|tickets|registration|resident|non[-\s]?resident|per\s+class|entry|cover|vip)\b",
    flags=re.I,
)
CONCESSION_PRICE_RE = re.compile(r"\$\s*\d+(?:\.\d{1,2})?\s+(?:hot\s+dogs?|food|drink|drinks|parking)", flags=re.I)
FREE_RE = re.compile(
    r"\b(?:free\s+(?:event|seminar|seminars|movie|street\s+festival|festival|concert|admission|class|workshop|program|one-hour\s+talk)|admission\s+(?:is\s+)?free|no\s+cost)\b",
    flags=re.I,
)
DROP_IN_RE = re.compile(
    r"\bdrop[-\s]?in\b|\bwalk[-\s]?in\b|\bopen\s+(?:play|pickleball|gym)\b|\bopen\s+to\s+(?:everyone|the\s+public)\b|\bno\s+registration\s+required\b",
    flags=re.I,
)
REGISTRATION_RE = re.compile(
    r"\bregistration\s+required\b|\bgiven\s+upon\s+registration\b|\bregistration\b.{0,60}\b(?:limited|spot|reserve|call)\b|\bregister\b|\bsign\s*up\b|\benroll\b|\breserve\s+your\s+spot\b",
    flags=re.I,
)
PUBLIC_MEETING_RE = re.compile(
    r"\b(?:public\s+meeting|city\s+council|board\s+meeting|committee\s+meeting|commission\s+meeting|advisory\s+group\s+meeting|town\s+hall|public\s+workshop|public\s+hearing|bid\s+opening|negotiations\s+meeting|information\s+session)\b",
    flags=re.I,
)
PUBLIC_DROP_IN_RE = re.compile(r"\b(?:farmers\s+market|art\s+walk|music\s+walk)\b", flags=re.I)
SERIES_CLASS_RE = re.compile(
    r"\b(?:yoga|tai\s*chi|line\s*dance|pottery|glass|stained\s+glass|bead|beadmaking|raku|wheel\s+throwing|silver\s+rings|polymer\s+clay|hula|circuit\s+training|cardio|camp\w*)\b",
    flags=re.I,
)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()


def extract_price_amounts(text: str) -> list[float]:
    amounts: list[float] = []
    for match in PRICE_RE.finditer(text):
        window = text[max(0, match.start() - 80) : match.end() + 80]
        if CONCESSION_PRICE_RE.search(window):
            continue
        if PRICE_CONTEXT_RE.search(window):
            amounts.append(float(match.group(1)))
    return amounts


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
    amounts = extract_price_amounts(text)
    has_free = bool(FREE_RE.search(text))
    has_drop_in = bool(DROP_IN_RE.search(text))
    no_registration_required = bool(re.search(r"\bno\s+registration\s+required\b", text, flags=re.I))
    vendor_registration_only = bool(
        re.search(r"\b(?:sign\s*up|register|registration)\b.{0,40}\bvendor\b|\bvendor\b.{0,40}\b(?:sign\s*up|register|registration)\b", text, flags=re.I)
    )
    has_registration = bool(REGISTRATION_RE.search(text)) and not no_registration_required and not vendor_registration_only
    looks_like_class_series = bool(SERIES_CLASS_RE.search(text))
    is_public_meeting = (category or "").lower() == "public meetings" or bool(PUBLIC_MEETING_RE.search(text))
    is_public_drop_in = bool(PUBLIC_DROP_IN_RE.search(text))

    if amounts:
        low = min(amounts)
        high = max(amounts)
        price_text = f"${low:g}" if low == high else f"${low:g}-${high:g}"
        payment_required: bool | None = True
        price_currency = "USD"
    elif has_free or is_public_meeting:
        low = high = None
        price_text = "Free"
        payment_required = False
        price_currency = "USD"
    else:
        low = high = None
        price_text = None
        payment_required = None
        price_currency = None

    if is_public_meeting and not has_registration:
        registration_required: bool | None = False
        access_type = "public_meeting"
        joinability = "public_attendance_ok"
    elif has_registration:
        registration_required = True
        access_type = "registration_required"
        joinability = "registration_needed"
    elif (has_free or has_drop_in or is_public_drop_in) and not has_registration:
        registration_required = False
        access_type = "drop_in"
        joinability = "drop_in_ok"
    elif looks_like_class_series:
        registration_required = None
        access_type = "class_series"
        joinability = "verify_mid_session_joinability"
    else:
        registration_required = None
        access_type = "unknown"
        joinability = "unknown"

    if (has_free or is_public_meeting) and (has_drop_in or is_public_meeting) and not has_registration:
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
        self.apply_access_metadata()

    def apply_access_metadata(self, *, overwrite_unknown: bool = False) -> None:
        metadata = infer_access_metadata(self.title, self.description, self.category, self.source_name)
        for key, value in metadata.items():
            current = getattr(self, key)
            if current is None and value is not None:
                setattr(self, key, value)
            elif overwrite_unknown and key in {"access_type", "joinability"} and current == "unknown" and value != "unknown":
                setattr(self, key, value)
            elif overwrite_unknown and key in {"payment_required", "registration_required"} and current is None:
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
