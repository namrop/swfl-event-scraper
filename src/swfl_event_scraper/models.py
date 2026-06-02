from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()


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
        }
