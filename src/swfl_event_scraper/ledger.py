"""The append-only event-candidate ledger.

The file is a ledger in the sense the 2026-09-09 ledger-form survey settled:
**one row is one event, rows are never mutated, and a correction is a new
row.** Nothing here rewrites a line.

Every row is a full snapshot of what was known about one candidate at one
moment. The ledger's *current* state is the fold: the latest row per `id`.
Three things append a row:

- a scrape, but only when a watched field actually changed (`record_type:
  observation`) — otherwise `last_seen_at` would churn 3,000 rows twice a week
  for no information;
- Luis, when he rates a candidate (`record_type: feedback`);
- a status change, when a row is printed, attended or passed
  (`record_type: status`).

`id` is deliberately NOT the old scraper's id. The 2026-09-09 audit found that
the Acubens hash mixed the source's own event id into the key, so the same
event listed by two sources could never merge. The ledger key is
`sha256(normalised title | start to the minute | normalised venue)[:16]`; the
old id survives in `source_row_id` so nothing is lost.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Iterator

LEDGER_SCHEMA = "event_candidate.v1"

# Fields a scrape compares to decide whether anything changed. `last_seen_at`
# is deliberately absent: a row that is merely still listed is not news.
WATCHED_FIELDS = (
    "title", "start", "end", "venue", "address", "city", "county",
    "lat", "lon", "distance_mi", "geo_precision", "source_name", "source_url",
    "category", "description", "interest_tags", "audience", "cost", "access",
    "rating", "rating_reason", "source_tags", "source_noisy",
)

_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^a-z0-9]+")


def _norm(text: str | None) -> str:
    return _WS.sub(" ", _NONWORD.sub(" ", (text or "").lower())).strip()


def _norm_start(start: str | None) -> str:
    """Normalise a start stamp to the minute, tolerating the shapes on disk."""
    raw = (start or "").strip().replace(" ", "T", 1)
    if not raw:
        return ""
    return raw[:16]


def candidate_id(title: str, start: str | None, venue: str | None) -> str:
    basis = "|".join([_norm(title), _norm_start(start), _norm(venue)])
    return sha256(basis.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def fold(path: str | Path) -> dict[str, dict[str, Any]]:
    """Latest row per id — the ledger's current state.

    A `feedback` or `status` row carries only its delta, so the fold layers
    rows in file order rather than replacing wholesale.
    """
    state: dict[str, dict[str, Any]] = {}
    for row in read_rows(path):
        rid = row.get("id")
        if not rid:
            continue
        if rid in state:
            state[rid] = {**state[rid], **{k: v for k, v in row.items() if v is not None or k in row}}
        else:
            state[rid] = dict(row)
    return state


def append_rows(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def changed(previous: dict[str, Any] | None, candidate: dict[str, Any]) -> bool:
    if previous is None:
        return True
    return any(previous.get(f) != candidate.get(f) for f in WATCHED_FIELDS)


def observation_row(
    *,
    candidate: dict[str, Any],
    previous: dict[str, Any] | None,
    seen_at: str | None = None,
) -> dict[str, Any]:
    """Build one `observation` snapshot, carrying forward frozen provenance."""
    at = seen_at or now_iso()
    row = dict(candidate)
    row["ledger_schema"] = LEDGER_SCHEMA
    row["record_type"] = "observation"
    row["last_seen_at"] = at
    if previous is not None:
        # first_seen_at is frozen provenance: a re-observation never resets it.
        row["first_seen_at"] = previous.get("first_seen_at") or at
        # Luis's judgement survives a re-scrape.
        for carried in ("feedback", "feedback_note", "feedback_at", "status"):
            if previous.get(carried) is not None:
                row[carried] = previous[carried]
    else:
        row.setdefault("first_seen_at", at)
    row.setdefault("feedback", None)
    row.setdefault("feedback_note", None)
    row.setdefault("feedback_at", None)
    row.setdefault("status", "candidate")
    return row


def feedback_row(
    *,
    row_id: str,
    feedback: int,
    note: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    if feedback not in (1, -1):
        raise ValueError("feedback must be +1 or -1")
    stamp = at or now_iso()
    return {
        "ledger_schema": LEDGER_SCHEMA,
        "record_type": "feedback",
        "id": row_id,
        "feedback": feedback,
        "feedback_note": note,
        "feedback_at": stamp,
        "last_seen_at": stamp,
    }


def status_row(*, row_id: str, status: str, note: str | None = None, at: str | None = None) -> dict[str, Any]:
    allowed = {"candidate", "printed", "attended", "passed"}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    stamp = at or now_iso()
    return {
        "ledger_schema": LEDGER_SCHEMA,
        "record_type": "status",
        "id": row_id,
        "status": status,
        "status_note": note,
        "status_at": stamp,
        "last_seen_at": stamp,
    }


# ---------------------------------------------------------------------------
# The radius rule
# ---------------------------------------------------------------------------

DEFAULT_RADIUS_MI = 25.0
# Rungs the widener climbs. The top rung is the demonstrated day-trip radius:
# St Petersburg and Sarasota were done in one day, about two hours each way.
RADIUS_LADDER: tuple[float, ...] = (10.0, 15.0, 25.0, 40.0, 60.0, 90.0, 120.0)


def within_radius(
    rows: Iterable[dict[str, Any]],
    radius_mi: float,
    *,
    include_unplaced: bool = False,
) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        d = r.get("distance_mi")
        if d is None:
            if include_unplaced:
                out.append(r)
            continue
        if d <= radius_mi:
            out.append(r)
    return out


def widen_until(
    rows: Iterable[dict[str, Any]],
    *,
    minimum: int,
    start_mi: float = DEFAULT_RADIUS_MI,
    ladder: tuple[float, ...] = RADIUS_LADDER,
    include_unplaced: bool = False,
) -> tuple[list[dict[str, Any]], float, bool]:
    """Widen the radius one rung at a time until at least `minimum` rows fall inside.

    Returns (rows, radius_used, satisfied). The newsroom calls this so a thin
    week produces a wider paper rather than an empty section, and so the paper
    can say in print how far it had to reach.
    """
    rows = list(rows)
    rungs = [r for r in ladder if r >= start_mi] or [start_mi]
    chosen = rungs[-1]
    for rung in rungs:
        hit = within_radius(rows, rung, include_unplaced=include_unplaced)
        if len(hit) >= minimum:
            return hit, rung, True
        chosen = rung
    return within_radius(rows, chosen, include_unplaced=include_unplaced), chosen, False
