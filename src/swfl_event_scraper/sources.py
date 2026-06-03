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
        parser="capecoral_webtrac_reader",
        notes="Official Parks & Recreation activity/event calendar. Direct requests hit Cloudflare; v0 uses a public reader fallback for the read-only calendar page.",
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
        name="Village of Estero Events",
        url="https://estero-fl.gov",
        kind=SourceKind.CIVIC_GOV,
        parser="tribe_events_api",
        notes="Official Village of Estero WordPress/The Events Calendar API; includes public meetings, workshops, closures, and civic/special events.",
    ),
    Source(
        name="Bonita Springs City Calendar",
        url="https://www.cityofbonitasprings.org/government/city_calendar",
        kind=SourceKind.CIVIC_GOV,
        parser="civiclive_calendar_pending",
        notes="Official CivicLive city calendar. Calendar is rendered by a React portlet; source is tracked, but a stable request adapter still needs endpoint/export handling.",
    ),
    Source(
        name="Bonita Springs City Approved Events",
        url="https://www.cityofbonitasprings.org/services___departments/communications_department/special_events/calendar_of_city_approved_events",
        kind=SourceKind.CIVIC_GOV,
        parser="civiclive_calendar_pending",
        notes="Official CivicLive city-approved special events calendar. Tracked as a separate Bonita Springs surface; June 2026 public view currently shows no events.",
    ),
    Source(
        name="MetroLagoons Brightwater Lagoon Events",
        url="https://www.metrolagoons.com/events?lagoon=brightwater",
        kind=SourceKind.VENUE,
        parser="metrolagoons_brightwater",
        notes="Brightwater Lagoon in North Fort Myers. Uses MetroLagoons AJAX event-calendar endpoint; events may require day ticket, ticket purchase, or resident membership.",
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
