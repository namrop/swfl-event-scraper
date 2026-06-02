from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceKind(Enum):
    CIVIC_GOV = "civic_gov"
    LIBRARY = "library"
    VENUE = "venue"
    AGGREGATOR = "aggregator"
    TICKETED = "ticketed"


@dataclass(frozen=True, slots=True)
class Source:
    name: str
    url: str
    kind: SourceKind
    parser: str
    notes: str = ""


SOURCES: tuple[Source, ...] = (
    Source(
        name="Cape Coral City Calendar",
        url="https://www.capecoral.gov/calendar.php",
        kind=SourceKind.CIVIC_GOV,
        parser="capecoral_revize",
        notes="Official Revize city calendar; includes Events and Public Meetings. Uses Revize JSON data handler.",
    ),
    Source(
        name="Cape Coral Parks WebTrac Events",
        url="https://web1.myvscloud.com/wbwsc/flcapecoralwt.wsc/search.html?display=Calendar&module=Event",
        kind=SourceKind.CIVIC_GOV,
        parser="unsupported_webtrac",
        notes="Official Parks & Recreation activity/event calendar; Cloudflare blocks plain requests, keep as first-class source for browser/manual adapter.",
    ),
    Source(
        name="Cape Coral Special Events",
        url="https://www.capecoral.gov/community/special_events/index.php",
        kind=SourceKind.CIVIC_GOV,
        parser="static_links",
        notes="Citywide annual special event hub: Red White & BOOM, Bike Night, Reindeer Run, etc.",
    ),
    Source(
        name="Lee County Parks & Recreation Events",
        url="https://www.leegov.com/parks/events",
        kind=SourceKind.CIVIC_GOV,
        parser="leegov_parks",
        notes="Official Lee County Parks & Recreation event calendar: special events, guided walks/tours, sports, Conservation 20/20 meetings.",
    ),
    Source(
        name="Lee County Library System Events",
        url="https://leelibrary.librarymarket.com/events/upcoming",
        kind=SourceKind.LIBRARY,
        parser="librarymarket",
        notes="LibraryMarket calendar for Lee County branches; free public library programs, meetings, STEAM, book clubs, ESL, performances.",
    ),
    Source(
        name="Fort Myers CivicEngage Calendar",
        url="https://fortmyers.gov/calendar.aspx",
        kind=SourceKind.CIVIC_GOV,
        parser="fort_myers_civicengage",
        notes="Official City of Fort Myers CivicEngage calendar; includes event and meeting calendars with schema.org microdata.",
    ),
    Source(
        name="Visit Fort Myers Events",
        url="https://www.visitfortmyers.com/events",
        kind=SourceKind.AGGREGATOR,
        parser="generic_jsonld",
        notes="Tourism-board aggregator; useful, but not a substitute for civic/public calendars.",
    ),
    Source(
        name="Eventbrite Cape Coral",
        url="https://www.eventbrite.com/d/fl--cape-coral/events/",
        kind=SourceKind.TICKETED,
        parser="eventbrite_optional",
        notes="Optional ticketed-event source; deliberately not the center of v0 coverage.",
    ),
)
