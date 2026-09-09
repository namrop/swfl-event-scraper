"""Semantic interest matching, audience attribution and the searcher's rating.

The vocabulary lives in ``vocabulary/interest_tags.yaml`` and is data, not code:
every tag carries the canon path it was read off, an audience default and a
weight. This module is the mechanism that applies it.

The rating is deliberately explainable. ``rating_reason`` names the tags that
fired, the costs that bit, and the distance band, so Luis's ±1 feedback lands
against a stated argument rather than a number. The feedback is what tunes the
weights later; nothing here learns on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

import yaml

VOCAB_PATH = Path(__file__).with_name("vocabulary") / "interest_tags.yaml"

# Distance bands, in miles from the household origin. The demonstrated
# day-trip radius is ~2h each way (St Petersburg and Sarasota in one day), so
# the penalty ramps instead of cliffing.
DISTANCE_BANDS: tuple[tuple[float, float, str], ...] = (
    (15.0, 0.0, "close to home"),
    (35.0, -0.25, "a short drive"),
    (60.0, -0.75, "a real drive"),
    (120.0, -1.5, "a day-trip drive"),
    (float("inf"), -2.5, "beyond the day-trip radius"),
)

BASE_RATING = 1.0
MAX_TAG_CONTRIBUTION = 3.5


@dataclass(frozen=True, slots=True)
class Rated:
    interest_tags: list[str]
    audience: str
    rating: float
    rating_reason: str
    costs: list[str]


@lru_cache(maxsize=1)
def load_vocabulary(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else VOCAB_PATH
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def _compiled() -> tuple[list[tuple[str, re.Pattern[str], dict]], list[tuple[str, re.Pattern[str], dict]]]:
    v = load_vocabulary()
    tags = [
        (name, re.compile(spec["match"], re.I), spec)
        for name, spec in v["tags"].items()
        if spec.get("match")
    ]
    costs = [
        (name, re.compile(spec["match"], re.I), spec)
        for name, spec in v["costs"].items()
        if spec.get("match")
    ]
    return tags, costs


def distance_band(distance_mi: float | None) -> tuple[float, str]:
    if distance_mi is None:
        return -0.25, "no location on the listing"
    for limit, penalty, label in DISTANCE_BANDS:
        if distance_mi <= limit:
            return penalty, label
    return -2.5, "beyond the day-trip radius"


def rate(
    *,
    title: str,
    description: str | None = None,
    category: str | None = None,
    venue: str | None = None,
    source_name: str | None = None,
    distance_mi: float | None = None,
    geo_precision: str | None = None,
    access: str | None = None,
    price_min: float | None = None,
    price_text: str | None = None,
    implied_tags: tuple[str, ...] | list[str] | None = None,
) -> Rated:
    tag_specs, cost_specs = _compiled()
    # Two haystacks. `event_text` is the event's own words; `all` adds the place
    # and the source. A tag declares which it reads, because a word can be true
    # of the building and false of the event inside it.
    event_text = " \n ".join(part for part in (title, description, category) if part)
    haystack = " \n ".join(
        part for part in (title, description, category, venue, source_name) if part
    )

    hits: list[tuple[str, float, str]] = []
    matched: set[str] = set()
    for name, pattern, spec in tag_specs:
        target = event_text if spec.get("scope") == "event_text" else haystack
        if pattern.search(target):
            hits.append((name, float(spec.get("weight", 1.0)), spec.get("audience", "both")))
            matched.add(name)

    # A source can declare tags every row it produces carries — Florida Rep is a
    # theatre, Naples Botanical Garden is a garden. More reliable than a regex
    # over a venue string, and it is how a person would reason.
    vocab = load_vocabulary()["tags"]
    for name in implied_tags or ():
        if name in matched:
            continue
        spec = vocab.get(name)
        if not spec:
            continue
        hits.append((name, float(spec.get("weight", 1.0)), spec.get("audience", "both")))
        matched.add(name)
    hits.sort(key=lambda h: -h[1])

    cost_hits: list[tuple[str, float, bool]] = []
    for name, pattern, spec in cost_specs:
        if pattern.search(haystack):
            cost_hits.append((name, float(spec.get("penalty", 0.0)), bool(spec.get("hard"))))

    tag_names = [h[0] for h in hits]
    tag_score = min(sum(h[1] for h in hits), MAX_TAG_CONTRIBUTION)

    audiences = {h[2] for h in hits}
    if not audiences:
        audience = "both"
    elif audiences == {"her"}:
        audience = "her"
    elif audiences == {"me"}:
        audience = "me"
    else:
        audience = "both"

    dist_penalty, dist_label = distance_band(distance_mi)
    if geo_precision in {"source_default", "none"} and dist_penalty < 0:
        # An unplaced row should not be punished twice for the same ignorance.
        dist_penalty = max(dist_penalty, -0.5)

    access_bonus = 0.0
    access_notes: list[str] = []
    if access in {"drop_in", "public_meeting"}:
        access_bonus += 0.25
        access_notes.append("no ticket needed")
    if (price_min is not None and price_min == 0) or (price_text or "").strip().lower() == "free":
        access_bonus += 0.25
        access_notes.append("free")

    hard = any(h[2] for h in cost_hits)
    cost_total = sum(h[1] for h in cost_hits)

    score = BASE_RATING + tag_score + dist_penalty + access_bonus - cost_total
    if hard:
        score = min(score, 0.5)
    rating = round(max(0.0, min(5.0, score)), 1)

    if tag_names:
        matched = ", ".join(tag_names[:4])
        more = f" (+{len(tag_names) - 4} more)" if len(tag_names) > 4 else ""
        reason = f"Matches {matched}{more}"
    else:
        reason = "No interest tag matched"
    reason += f"; {dist_label}"
    if distance_mi is not None:
        reason += f" ({distance_mi:g} mi, {geo_precision})"
    if access_notes:
        reason += "; " + " and ".join(access_notes)
    if cost_hits:
        reason += "; down-rated for " + ", ".join(n for n, _, _ in cost_hits)
    if hard:
        reason += " (hard exclusion)"
    reason += f". Searcher score {rating}/5 under interest_tags.v1."

    return Rated(
        interest_tags=tag_names,
        audience=audience,
        rating=rating,
        rating_reason=reason,
        costs=[n for n, _, _ in cost_hits],
    )
