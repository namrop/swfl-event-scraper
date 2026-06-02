from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scrape import scrape_sources
from .sources import SOURCES
from .storage import upsert_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape SWFL local/civic events into SQLite.")
    parser.add_argument("--db", default="data/events.sqlite3", help="SQLite output path")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Limit to source name substring; can be passed multiple times",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = list(SOURCES)
    if args.source:
        needles = [needle.lower() for needle in args.source]
        selected = [source for source in selected if any(needle in source.name.lower() for needle in needles)]
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


if __name__ == "__main__":
    raise SystemExit(main())
