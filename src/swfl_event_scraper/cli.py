from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from . import ledger as L
from .geo import HOME_LABEL, HOME_LAT, HOME_LON
from .rows import candidate_from_event, candidate_from_sqlite_row
from .scrape import scrape_sources
from .sources import SOURCES
from .storage import upsert_events

DEFAULT_DB = "data/events.sqlite3"
DEFAULT_LEDGER = "/srv/pharos/atrium/canon/12_runtime/ledgers/events/event_candidates.jsonl"


def _require_ledger(path: str) -> bool:
    """A missing ledger must be an error, not an empty answer.

    `read_rows` yields nothing for a path that is not there, so a mistyped
    --ledger used to produce a confident "0 candidates" — which, in the
    newspaper's composer, is an empty events section rather than a failure.
    Found the hard way: a query run from the wrong working directory.
    """
    if Path(path).exists():
        return True
    print(f"ledger not found: {path}", file=sys.stderr)
    return False


def _select(needles: list[str]):
    selected = list(SOURCES)
    if needles:
        low = [n.lower() for n in needles]
        selected = [s for s in selected if any(n in s.name.lower() for n in low)]
    return selected


def _source_defaults() -> dict:
    return {s.name: s.default_place() for s in SOURCES if s.default_place() is not None}


# ---------------------------------------------------------------- scrape ----

def cmd_scrape(args) -> int:
    selected = _select(args.source)
    events, health = scrape_sources(selected)
    written = upsert_events(Path(args.db), events)
    summary = {
        "selected_sources": len(selected),
        "events_scraped": len(events),
        "events_written": written,
        "db": str(args.db),
        "health": health,
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"scraped={len(events)} written={written} db={args.db}")
        for row in health:
            msg = f" ({row['message']})" if row.get("message") else ""
            print(f"- {row['source']}: {row['events']} {row['status']}{msg}")
    return 0


# --------------------------------------------------------- ledger-append ----

def _append_candidates(ledger_path: str, candidates: list[dict], *, seen_at: str | None = None) -> dict:
    state = L.fold(ledger_path)
    rows, new, changed = [], 0, 0
    for cand in candidates:
        prev = state.get(cand["id"])
        if not L.changed(prev, cand):
            continue
        rows.append(L.observation_row(candidate=cand, previous=prev, seen_at=seen_at))
        if prev is None:
            new += 1
        else:
            changed += 1
    appended = L.append_rows(ledger_path, rows)
    return {"appended": appended, "new": new, "changed": changed, "considered": len(candidates)}


def cmd_ledger_append(args) -> int:
    """Scrape, then append only what is new or actually different."""
    selected = _select(args.source)
    events, health = scrape_sources(selected)
    upsert_events(Path(args.db), events)
    by_name = {s.name: s for s in SOURCES}
    candidates = [
        candidate_from_event(e, by_name.get(e.source_name) or by_name[s.name])
        for s in selected
        for e in events
        if e.source_name == s.name
    ]
    result = _append_candidates(args.ledger, candidates)
    result["health"] = health
    result["ledger"] = args.ledger
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        # One line for the cron delivery: --no-agent jobs with empty stdout are
        # silent, and silence here would hide a source going dark.
        live = [h for h in health if h["status"] == "ok"]
        errs = [h for h in health if h["status"] == "error"]
        print(
            f"events ledger: +{result['new']} new, {result['changed']} changed, "
            f"{result['considered']} seen from {len(live)}/{len(selected)} live sources"
            + (f"; ERRORS: {', '.join(h['source'] for h in errs)}" if errs else "")
        )
    return 0


# --------------------------------------------------------------- migrate ----

def _iso_utc(stamp: str | None) -> str | None:
    """The retired SQLite wrote `datetime('now')` — naive, space-separated UTC.

    Preserved as the same instant, correctly labelled, rather than reformatted
    into a local time it never was. This is a provenance improvement: the
    Acubens stamps were UTC and did not say so.
    """
    if not stamp:
        return None
    s = stamp.strip()
    if "T" in s:
        return s
    if " " in s and len(s) >= 19:
        return s.replace(" ", "T", 1) + "+00:00"
    return s


def cmd_migrate(args) -> int:
    """Migrate an existing SQLite database into the ledger, once."""
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM events")]
    conn.close()
    defaults = _source_defaults()

    seen: dict[str, dict] = {}
    seen_last: dict[str, str] = {}
    collapsed = 0
    for r in rows:
        cand = candidate_from_sqlite_row(r, defaults)
        # Acubens rows keep their ORIGINAL first_seen_at: the ledger inherits
        # three months of provenance rather than pretending today is day one.
        cand["first_seen_at"] = _iso_utc(r.get("first_seen_at") or r.get("scraped_at"))
        cand["migrated_from"] = args.migrated_from
        seen_last[cand["id"]] = r.get("last_seen_at") or r.get("scraped_at")
        if cand["id"] in seen:
            collapsed += 1
        seen[cand["id"]] = cand

    out = []
    state = L.fold(args.ledger)
    for cand in seen.values():
        prev = state.get(cand["id"])
        row = L.observation_row(
            candidate=cand,
            previous=prev,
            seen_at=args.last_seen_at or _iso_utc(
                (r_last := seen_last.get(cand["id"])) and r_last
            ) or cand.get("first_seen_at"),
        )
        row["first_seen_at"] = cand["first_seen_at"]
        row["record_type"] = "observation"
        out.append(row)
    appended = 0 if args.dry_run else L.append_rows(args.ledger, out)

    by_source: dict[str, int] = {}
    for c in seen.values():
        by_source[c["source_name"]] = by_source.get(c["source_name"], 0) + 1
    summary = {
        "sqlite_rows": len(rows),
        "distinct_candidates": len(seen),
        "collapsed_by_new_key": collapsed,
        "appended": appended,
        "dry_run": args.dry_run,
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
    }
    print(json.dumps(summary, indent=2))
    return 0


# ----------------------------------------------------------------- query ----

def cmd_rerate(args) -> int:
    """Re-score every candidate under the current vocabulary, append the diffs.

    A vocabulary fix is a correction, and in an append-only ledger a correction
    is a new row. This appends one `observation` per candidate whose tags,
    audience, rating or reason changed, and touches nothing else — Luis's
    feedback and the row's status carry forward, and `first_seen_at` is frozen.
    """
    from .interest import load_vocabulary, rate

    version = load_vocabulary()["version"]
    implied = {s.name: s.implied_tags for s in SOURCES}
    state = L.fold(args.ledger)
    rows, changed = [], 0
    for cand in state.values():
        if cand.get("record_type") not in (None, "observation", "feedback", "status"):
            continue
        r = rate(
            title=cand.get("title") or "",
            description=cand.get("description"),
            category=cand.get("category"),
            venue=cand.get("venue"),
            source_name=cand.get("source_name"),
            distance_mi=cand.get("distance_mi"),
            geo_precision=cand.get("geo_precision"),
            access=cand.get("access"),
            price_min=(cand.get("cost") or {}).get("price_min"),
            price_text=(cand.get("cost") or {}).get("price_text"),
            implied_tags=implied.get(cand.get("source_name"), ()),
        )
        if (
            cand.get("interest_tags") == r.interest_tags
            and cand.get("interest_costs") == r.costs
            and cand.get("audience") == r.audience
            and cand.get("rating") == r.rating
            and cand.get("rating_reason") == r.rating_reason
        ):
            continue
        changed += 1
        updated = dict(cand)
        updated.update(
            interest_tags=r.interest_tags,
            interest_costs=r.costs,
            audience=r.audience,
            rating=r.rating,
            rating_reason=r.rating_reason,
            rerated_under=version,
        )
        updated.pop("status_note", None)
        updated.pop("status_at", None)
        rows.append(L.observation_row(candidate=updated, previous=cand))
    appended = 0 if args.dry_run else L.append_rows(args.ledger, rows)
    print(json.dumps({"vocabulary": version, "candidates": len(state),
                      "rescored": changed, "appended": appended,
                      "dry_run": args.dry_run}, indent=2))
    return 0


def cmd_query(args) -> int:
    if not _require_ledger(args.ledger):
        return 2
    state = L.fold(args.ledger)
    rows = [r for r in state.values() if not r.get("is_spam")]
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.audience:
        rows = [r for r in rows if r.get("audience") in (args.audience, "both")]
    if args.tag:
        rows = [r for r in rows if any(t in (r.get("interest_tags") or []) for t in args.tag)]
    if args.min_rating is not None:
        rows = [r for r in rows if (r.get("rating") or 0) >= args.min_rating]
    if args.since:
        rows = [r for r in rows if (r.get("start") or "") >= args.since]
    if args.until:
        rows = [r for r in rows if (r.get("start") or "") <= args.until]

    if args.widen_until:
        rows, radius, satisfied = L.widen_until(
            rows,
            minimum=args.widen_until,
            start_mi=args.radius_mi,
            include_unplaced=args.include_unplaced,
        )
    else:
        radius, satisfied = args.radius_mi, True
        rows = L.within_radius(rows, radius, include_unplaced=args.include_unplaced)

    rows.sort(key=lambda r: (-(r.get("rating") or 0), r.get("start") or ""))
    rows = rows[: args.limit]
    out = {
        "origin": {"lat": HOME_LAT, "lon": HOME_LON, "label": HOME_LABEL},
        "radius_mi": radius,
        "radius_satisfied": satisfied,
        "count": len(rows),
        "events": rows if args.json else None,
    }
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
    else:
        print(f"# radius {radius} mi from {HOME_LABEL}; {len(rows)} candidate(s)"
              + ("" if satisfied else " [ladder exhausted]"))
        for r in rows:
            d = r.get("distance_mi")
            print(f"{r.get('rating')}  {(r.get('start') or '')[:16]:<16} "
                  f"{(r.get('title') or '')[:56]:<58} "
                  f"{(str(d) + ' mi') if d is not None else '  -  ':>8}  "
                  f"{r.get('audience'):<5} {','.join(r.get('interest_tags') or [])[:44]}")
            print(f"     {r.get('id')}  {r.get('source_name')}")
    return 0


# -------------------------------------------------------------- feedback ----

def cmd_feedback(args) -> int:
    if not _require_ledger(args.ledger):
        return 2
    state = L.fold(args.ledger)
    if args.id not in state:
        print(f"no candidate with id {args.id} in {args.ledger}", file=sys.stderr)
        return 1
    row = L.feedback_row(row_id=args.id, feedback=args.score, note=args.note)
    L.append_rows(args.ledger, [row])
    print(f"appended feedback {args.score:+d} for {state[args.id].get('title')!r}")
    return 0


def cmd_status(args) -> int:
    if not _require_ledger(args.ledger):
        return 2
    state = L.fold(args.ledger)
    if args.id not in state:
        print(f"no candidate with id {args.id} in {args.ledger}", file=sys.stderr)
        return 1
    L.append_rows(args.ledger, [L.status_row(row_id=args.id, status=args.value, note=args.note)])
    print(f"appended status {args.value} for {state[args.id].get('title')!r}")
    return 0


def cmd_health(args) -> int:
    """Read-only: what the ledger holds and where the scraper stands."""
    if not _require_ledger(args.ledger):
        return 2
    state = L.fold(args.ledger)
    by_source, by_precision, rated = {}, {}, 0
    for r in state.values():
        by_source[r.get("source_name")] = by_source.get(r.get("source_name"), 0) + 1
        by_precision[r.get("geo_precision")] = by_precision.get(r.get("geo_precision"), 0) + 1
        if r.get("feedback") is not None:
            rated += 1
    out = {
        "ledger": args.ledger,
        "rows_on_disk": sum(1 for _ in L.read_rows(args.ledger)),
        "distinct_candidates": len(state),
        "with_luis_feedback": rated,
        "origin": {"lat": HOME_LAT, "lon": HOME_LON},
        "sources_registered": len(SOURCES),
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "by_geo_precision": by_precision,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swfl-events",
        description="Scrape SWFL local/civic events and keep the household event-candidate ledger.",
    )
    sub = parser.add_subparsers(dest="command")

    def add_common(p, ledger=True):
        p.add_argument("--db", default=DEFAULT_DB, help="SQLite working store")
        if ledger:
            p.add_argument("--ledger", default=DEFAULT_LEDGER, help="append-only JSONL ledger")

    s = sub.add_parser("scrape", help="Scrape sources into the SQLite working store")
    add_common(s, ledger=False)
    s.add_argument("--source", action="append", default=[])
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scrape)

    s = sub.add_parser("ledger-append", help="Scrape, then append new/changed rows to the ledger")
    add_common(s)
    s.add_argument("--source", action="append", default=[])
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_ledger_append)

    s = sub.add_parser("migrate", help="One-shot migration of an existing SQLite database into the ledger")
    add_common(s)
    s.add_argument("--migrated-from", default="acubens:~/Code/swfl-event-scraper/data/events.sqlite3")
    s.add_argument("--last-seen-at", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_migrate)

    s = sub.add_parser("rerate", help="Re-score every candidate under the current vocabulary")
    s.add_argument("--ledger", default=DEFAULT_LEDGER)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_rerate)

    s = sub.add_parser("query", help="Radius query over the ledger's current state")
    s.add_argument("--ledger", default=DEFAULT_LEDGER)
    s.add_argument("--radius-mi", type=float, default=L.DEFAULT_RADIUS_MI)
    s.add_argument("--widen-until", type=int, default=None,
                   help="widen the radius one rung at a time until at least N candidates fall inside")
    s.add_argument("--include-unplaced", action="store_true",
                   help="include rows with no distance (geo_precision virtual/none)")
    s.add_argument("--audience", choices=["me", "her", "both"])
    s.add_argument("--tag", action="append", default=[])
    s.add_argument("--status", default=None)
    s.add_argument("--min-rating", type=float, default=None)
    s.add_argument("--since", default=None, help="ISO start floor, e.g. 2026-09-10")
    s.add_argument("--until", default=None)
    s.add_argument("--limit", type=int, default=40)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_query)

    s = sub.add_parser("feedback", help="Record Luis's +1 / -1 on a candidate")
    s.add_argument("--ledger", default=DEFAULT_LEDGER)
    s.add_argument("id")
    s.add_argument("score", type=int, choices=[1, -1])
    s.add_argument("--note", default=None)
    s.set_defaults(func=cmd_feedback)

    s = sub.add_parser("status", help="Mark a candidate printed / attended / passed")
    s.add_argument("--ledger", default=DEFAULT_LEDGER)
    s.add_argument("id")
    s.add_argument("value", choices=["candidate", "printed", "attended", "passed"])
    s.add_argument("--note", default=None)
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("health", help="Read-only ledger and source health")
    s.add_argument("--ledger", default=DEFAULT_LEDGER)
    s.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    known = {"scrape", "ledger-append", "migrate", "rerate", "query",
             "feedback", "status", "health", "-h", "--help"}
    if not argv or argv[0] not in known:
        # Back-compat: the pre-ledger CLI took only flags and always scraped.
        argv = ["scrape", *argv]
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
