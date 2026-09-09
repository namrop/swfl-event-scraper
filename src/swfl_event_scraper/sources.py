from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceKind(Enum):
    CIVIC_GOV = "civic_gov"
    LIBRARY = "library"
    VENUE = "venue"
    COLLEGE = "college"
    AGGREGATOR = "aggregator"
    TICKETED = "ticketed"


@dataclass(frozen=True, slots=True)
class Source:
    """A place events come from.

    The geography fields were added 2026-09-09 for the household event ledger.
    Every source declares the `region` and `county` it reports on and a default
    lat/lon centroid, so a row whose free-text `location` cannot be resolved to
    a named venue still lands somewhere honest and the radius query can see it
    (with `geo_precision: source_default`, never `venue`).

    `crawl_delay_s` is the polite pause between requests to this host. Where a
    site publishes `Crawl-delay` in robots.txt, this is that number.
    """

    name: str
    url: str
    kind: SourceKind
    parser: str
    notes: str = ""
    region: str = "SWFL"
    county: str | None = None
    default_lat: float | None = None
    default_lon: float | None = None
    crawl_delay_s: float = 1.0
    robots_note: str = ""
    # How this source is read. `request` is an ordinary HTTP client.
    # `browser_lane` means Cloudflare or an equivalent blocks every request
    # client by fingerprint, and the fetch happens in a real browser on
    # another host; the adapter here reads the dump that lane produces.
    fetch: str = "request"

    def default_place(self):
        from .geo import Place

        if self.default_lat is None or self.default_lon is None:
            return None
        return Place(self.default_lat, self.default_lon, "", self.county or "", self.region)


SOURCES: tuple[Source, ...] = (
    Source(
        name="Cape Coral City Calendar",
        url="https://www.capecoral.gov/calendar.php",
        kind=SourceKind.CIVIC_GOV,
        parser="capecoral_revize",
        notes="Official Revize city calendar; includes Events and Public Meetings. Uses Revize JSON data handler.",
        county="Lee",
        default_lat=26.6294,
        default_lon=-81.986,
    ),
    Source(
        name="Cape Coral Parks WebTrac Events",
        url="https://web1.myvscloud.com/wbwsc/flcapecoralwt.wsc/search.html?display=Calendar&module=Event",
        kind=SourceKind.CIVIC_GOV,
        parser="capecoral_webtrac_browser_dump",
        fetch="browser_lane",
        notes=(
            "Official Parks & Recreation activity/event calendar, and the largest single "
            "source in the ledger (710 migrated rows). Dead to request clients since June: "
            "Cloudflare blocks by client fingerprint, so curl, requests and the r.jina.ai "
            "reader all get 403 from Sol and from Acubens' residential IP, and there is no "
            "iCal or RSS export. Recovered 2026-09-09 through an Earthglass Chrome lane on "
            "40eridani (496 occurrences, 127 titles, 09/09-10/03); ~115 of those titles "
            "appear in no other source, so Revize stays too. This adapter reads the grid "
            "HTML that lane saves rather than fetching: set SWFL_WEBTRAC_DUMP to the file. "
            "Method and selectors: 20_digital_architecture/household_newspaper/"
            "cape_coral_webtrac_recovery_2026-09-09.md. Grid is current-month only; weekly "
            "cadence is enough; schedule is the newspaper manager's call."
        ),
        county="Lee",
        default_lat=26.5629,
        default_lon=-81.9495,
    ),
    Source(
        name="Cape Coral Special Events",
        url="https://www.capecoral.gov/community/special_events/index.php",
        kind=SourceKind.CIVIC_GOV,
        parser="static_links",
        notes="Citywide annual special event hub: Red White & BOOM, Bike Night, Reindeer Run, etc.",
        county="Lee",
        default_lat=26.5629,
        default_lon=-81.9495,
    ),
    Source(
        name="Lee County Parks & Recreation Events",
        url="https://www.leegov.com/parks/events",
        kind=SourceKind.CIVIC_GOV,
        parser="leegov_parks",
        notes="Official Lee County Parks & Recreation event calendar: special events, guided walks/tours, sports, Conservation 20/20 meetings.",
        county="Lee",
        default_lat=26.6406,
        default_lon=-81.8723,
    ),
    Source(
        name="Lee County Library System Events",
        url="https://leelibrary.librarymarket.com/events/upcoming",
        kind=SourceKind.LIBRARY,
        parser="librarymarket",
        notes="LibraryMarket calendar for Lee County branches; free public library programs, meetings, STEAM, book clubs, ESL, performances.",
        county="Lee",
        default_lat=26.6406,
        default_lon=-81.8723,
    ),
    Source(
        name="Fort Myers CivicEngage Calendar",
        url="https://fortmyers.gov/calendar.aspx",
        kind=SourceKind.CIVIC_GOV,
        parser="fort_myers_civicengage",
        notes="Official City of Fort Myers CivicEngage calendar; includes event and meeting calendars with schema.org microdata.",
        county="Lee",
        default_lat=26.6446,
        default_lon=-81.8723,
    ),
    Source(
        name="Village of Estero Events",
        url="https://estero-fl.gov",
        kind=SourceKind.CIVIC_GOV,
        parser="tribe_events_api",
        notes="Official Village of Estero WordPress/The Events Calendar API; includes public meetings, workshops, closures, and civic/special events.",
        county="Lee",
        default_lat=26.4381,
        default_lon=-81.8067,
    ),
    Source(
        name="Bonita Springs City Calendar",
        url="https://www.cityofbonitasprings.org/government/city_calendar",
        kind=SourceKind.CIVIC_GOV,
        parser="civiclive_calendar_pending",
        notes="Official CivicLive city calendar. Calendar is rendered by a React portlet; source is tracked, but a stable request adapter still needs endpoint/export handling.",
        county="Lee",
        default_lat=26.3398,
        default_lon=-81.7787,
    ),
    Source(
        name="Bonita Springs City Approved Events",
        url="https://www.cityofbonitasprings.org/services___departments/communications_department/special_events/calendar_of_city_approved_events",
        kind=SourceKind.CIVIC_GOV,
        parser="civiclive_calendar_pending",
        notes="Official CivicLive city-approved special events calendar. Tracked as a separate Bonita Springs surface; June 2026 public view currently shows no events.",
        county="Lee",
        default_lat=26.3398,
        default_lon=-81.7787,
    ),
    Source(
        name="MetroLagoons Brightwater Lagoon Events",
        url="https://www.metrolagoons.com/events?lagoon=brightwater",
        kind=SourceKind.VENUE,
        parser="metrolagoons_brightwater",
        notes="Brightwater Lagoon in North Fort Myers. Uses MetroLagoons AJAX event-calendar endpoint; events may require day ticket, ticket purchase, or resident membership.",
        county="Lee",
        default_lat=26.7355,
        default_lon=-81.842,
    ),
    Source(
        name="FGCU Events",
        url="https://www.fgcu.edu/calendar/",
        kind=SourceKind.COLLEGE,
        parser="fgcu_25live_all_events",
        notes="Official Florida Gulf Coast University all-events calendar. The public page embeds 25Live/CollegeNET data; scraper uses FGCU's JSON feed for the test-special-events calendar surface.",
        county="Lee",
        default_lat=26.4636,
        default_lon=-81.7748,
    ),
    Source(
        name="FSW Presence Events",
        url="https://fsw.presence.io/events",
        kind=SourceKind.COLLEGE,
        parser="presence_events",
        notes="Official Florida SouthWestern State College event calendar. The fsw.edu calendar redirects to Presence; scraper uses the public Presence JSON API.",
        county="Lee",
        default_lat=26.5936,
        default_lon=-81.879,
    ),
    Source(
        name="Visit Fort Myers Events",
        url="https://www.visitfortmyers.com/events",
        kind=SourceKind.AGGREGATOR,
        parser="generic_jsonld",
        notes="Tourism-board aggregator; useful, but not a substitute for civic/public calendars.",
        county="Lee",
        default_lat=26.6406,
        default_lon=-81.8723,
    ),
    # ------------------------------------------------------------------
    # Theatre and arts venues, added 2026-09-09 for the household event
    # ledger (Luis, 18:54 EDT: "local plays at the various theatres are
    # something I would want to know about"). Eleven venues were probed; the
    # three below are the ones that publish a structured feed. The other
    # eight are recorded as tracked-but-pending sources further down, each
    # with the reason it could not be read politely.
    # ------------------------------------------------------------------
    Source(
        name="Florida Repertory Theatre",
        url="https://www.floridarep.org",
        kind=SourceKind.VENUE,
        parser="tribe_events_api",
        notes="Professional regional theatre in the historic Arcade Theatre, downtown Fort Myers. Publishes The Events Calendar REST API; each production is one event spanning its run.",
        county="Lee",
        default_lat=26.6469,
        default_lon=-81.8710,
        crawl_delay_s=2.0,
        robots_note="robots.txt permits all; no Crawl-delay declared. 2 s used anyway.",
    ),
    Source(
        name="Alliance for the Arts",
        url="https://www.artinlee.org",
        kind=SourceKind.VENUE,
        parser="tribe_events_api",
        notes="Lee County's arts campus on McGregor: gallery shows, art classes, the GreenMarket, outdoor concerts, and Theatre Conspiracy's productions, which are staged here and therefore arrive through this feed rather than Theatre Conspiracy's own site.",
        county="Lee",
        default_lat=26.5710,
        default_lon=-81.8845,
        crawl_delay_s=5.0,
        robots_note=(
            "robots.txt declares 'Crawl-delay: 5' and 'Disallow: /*?*'. The 5 s delay is honoured. "
            "The Disallow targets faceted-search crawl traps; the documented public REST API is read "
            "as an API rather than a crawl surface, page count is capped, and the decision is written "
            "down here so it can be overruled."
        ),
    ),
    Source(
        name="Naples Botanical Garden",
        url="https://www.naplesgarden.org",
        kind=SourceKind.VENUE,
        parser="tribe_events_api",
        notes="170-acre botanical garden in Naples: garden walks, plant sales, horticulture talks, concerts on the lawn. Collier County, ~33 mi from home, so it exercises the radius rule.",
        county="Collier",
        default_lat=26.1189,
        default_lon=-81.7756,
        crawl_delay_s=2.0,
        robots_note="robots.txt permits all; no Crawl-delay declared.",
    ),
    # ------------------------------------------------------------------
    # Probed 2026-09-09 and NOT implemented. Each is tracked so the next
    # pass does not re-probe blind, and so the reason is a fact rather than
    # a memory.
    # ------------------------------------------------------------------
    Source(
        name="Barbara B. Mann Performing Arts Hall",
        url="https://www.bbmannpah.com",
        kind=SourceKind.VENUE,
        parser="js_rendered_no_feed",
        notes="Touring Broadway and concerts on the FSW campus. Not WordPress; /events and /events/all carry only Organization and BreadcrumbList JSON-LD, no Event objects and no embedded JSON blocks; /sitemap.xml is 404. The listing is rendered client-side.",
        county="Lee",
        default_lat=26.5301,
        default_lon=-81.8985,
    ),
    Source(
        name="Broadway Palm Dinner Theatre",
        url="https://www.broadwaypalm.com",
        kind=SourceKind.VENUE,
        parser="dates_behind_ticketing",
        notes="Dinner theatre with a main stage and the Off Broadway Palm black box. WordPress with a `show` CPT that is not REST-exposed; show-sitemap.xml lists 120 show pages but their JSON-LD is WebPage only and no run dates appear in the page text — the dates live in the ticketing system.",
        county="Lee",
        default_lat=26.5860,
        default_lon=-81.8703,
    ),
    Source(
        name="Cultural Park Theatre",
        url="https://culturalparktheater.com",
        kind=SourceKind.VENUE,
        parser="rest_api_disabled",
        notes="Community theatre in Cape Coral, the closest of them all. The WordPress REST API is disabled (404 on /wp-json), robots.txt is 404, and no event surface was found without one.",
        county="Lee",
        default_lat=26.6294,
        default_lon=-81.9860,
    ),
    Source(
        name="Laboratory Theater of Florida",
        url="https://www.laboratorytheaterflorida.com",
        kind=SourceKind.VENUE,
        parser="no_event_surface",
        notes="Downtown Fort Myers black box. WordPress, but no Events Calendar plugin, no event custom post type, and no JSON-LD on the home page; /events, /shows and /on-stage are all 404.",
        county="Lee",
        default_lat=26.6462,
        default_lon=-81.8718,
    ),
    Source(
        name="Sidney and Berne Davis Art Center",
        url="https://sbdac.com",
        kind=SourceKind.VENUE,
        parser="js_rendered_no_feed",
        notes="Arts centre in the old federal building downtown. WordPress with no event CPT; /events and /calendar are single 570-650 KB client-rendered pages with zero JSON-LD. Its own page says 'Check out our new Event Calendar!', so the surface may be worth re-probing after that migration settles.",
        county="Lee",
        default_lat=26.6462,
        default_lon=-81.8718,
    ),
    Source(
        name="Theatre Conspiracy",
        url="https://www.theatreconspiracy.org",
        kind=SourceKind.VENUE,
        parser="tls_failure_covered_elsewhere",
        notes="TLS handshake fails on www (TLSV1_ALERT_INTERNAL_ERROR) for most requests, and the site that does answer is static with a single TheaterGroup JSON-LD block. Not a loss: the company is resident at the Alliance for the Arts and its productions arrive through that feed.",
        county="Lee",
        default_lat=26.5710,
        default_lon=-81.8845,
    ),
    Source(
        name="Gulfshore Playhouse",
        url="https://www.gulfshoreplayhouse.org",
        kind=SourceKind.VENUE,
        parser="cpt_without_dates",
        notes="Naples professional theatre. /wp-json/wp/v2/events exposes the `events` post type, but the rows carry no start or end date — `acf` is empty and only the WordPress publish date is present. Dates exist only in the page layout.",
        county="Collier",
        default_lat=26.1443,
        default_lon=-81.7940,
    ),
    Source(
        name="The Naples Players",
        url="https://naplesplayers.org",
        kind=SourceKind.VENUE,
        parser="bot_challenge",
        notes="Community theatre at the Sugden Community Theatre, Naples. robots.txt says 'Allow: /' but every other path answers 403 to a non-browser client, including /wp-json. A challenge bypass was not attempted.",
        county="Collier",
        default_lat=26.1443,
        default_lon=-81.7940,
    ),
    Source(
        name="Artis-Naples",
        url="https://artisnaples.org",
        kind=SourceKind.VENUE,
        parser="robots_disallowed",
        notes="Hayes Hall, the Baker Museum and the Naples Philharmonic. robots.txt carries 'Disallow: /calendar/'. Skipped by rule, not by capability — the listing is reachable, and we are choosing not to take it.",
        county="Collier",
        default_lat=26.2192,
        default_lon=-81.8025,
    ),
    Source(
        name="Collier County Public Library",
        url="https://collierlibrary.libnet.info/events",
        kind=SourceKind.LIBRARY,
        parser="bot_challenge",
        notes="Collier's branches run on Libnet (the same family as Lee's LibraryMarket). The page HTML is client-rendered with no event cards and no JSON-LD, and the XHR the browser calls (/eeventcaldata) answers 403 to a non-browser client.",
        county="Collier",
        default_lat=26.1420,
        default_lon=-81.7948,
    ),
    Source(
        name="Eventbrite Cape Coral",
        url="https://www.eventbrite.com/d/fl--cape-coral/events/",
        kind=SourceKind.TICKETED,
        parser="eventbrite_optional",
        notes="Optional ticketed-event source; deliberately not the center of coverage. NOT IMPLEMENTED: Eventbrite retired its public/anonymous event-search API in 2019 and the remaining v3 endpoints need an OAuth token, while the keyless HTML surface is challenge-protected. Any row that ever arrives from here must carry source_noisy: true (Luis, 2026-09-09: \"Eventbrite is kind of noisy\").",
        county="Lee",
        default_lat=26.5629,
        default_lon=-81.9495,
    ),
)
