"""Geography for the household event ledger.

Two rules make this honest rather than merely present:

1. **No geocoder is called.** Every coordinate here is a hand-entered venue or
   a source centroid. 3,209 migrated rows carry free-text `location` strings
   like "Marieb Hall 344 - ICU Lab Restricted"; running those through a
   geocoding service would produce confident nonsense and would be a lot of
   traffic for a household paper.
2. **Every row records how it was placed.** `geo_precision` is one of
   ``venue`` | ``city`` | ``source_default`` | ``virtual`` | ``none``, so
   ``distance_mi`` can never quietly claim more than it knows. A radius query
   that wants only trustworthy distances filters on precision.

The household origin is the NWS gridpoint constant already recorded in the
newspaper profile note (26.5629, -81.9495 — Cape Coral).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
import re

# Household origin. Source: the weather gridpoint constant in
# 20_digital_architecture/household_newspaper/optical_foundry_profile_and_templating_ladder_2026-09-09.md §3.
HOME_LAT = 26.5629
HOME_LON = -81.9495
HOME_LABEL = "Cape Coral, FL (NWS gridpoint constant)"

EARTH_RADIUS_MI = 3958.7613


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dp = p2 - p1
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * asin(sqrt(a))


def distance_from_home_mi(lat: float, lon: float) -> float:
    return round(haversine_mi(HOME_LAT, HOME_LON, lat, lon), 2)


@dataclass(frozen=True, slots=True)
class Place:
    lat: float
    lon: float
    city: str
    county: str
    region: str = "SWFL"


# Venue table. Keys are lowercase substrings matched against the event's
# `location` string, longest key first, so "cape coral-lee county public
# library" wins over "cape coral". Coordinates are hand-entered.
VENUES: dict[str, Place] = {
    # --- Cape Coral -----------------------------------------------------
    "1015 cultural park": Place(26.6294, -81.9860, "Cape Coral", "Lee"),
    "cultural park blvd": Place(26.6294, -81.9860, "Cape Coral", "Lee"),
    "cultural park boulevard": Place(26.6294, -81.9860, "Cape Coral", "Lee"),
    "cultural park theat": Place(26.6294, -81.9860, "Cape Coral", "Lee"),
    "815 nicholas": Place(26.6295, -81.9707, "Cape Coral", "Lee"),
    "lake kennedy": Place(26.6349, -81.9868, "Cape Coral", "Lee"),
    "rotary park": Place(26.5455, -81.9926, "Cape Coral", "Lee"),
    "four freedoms": Place(26.5566, -81.9483, "Cape Coral", "Lee"),
    "four mile cove": Place(26.5905, -81.9309, "Cape Coral", "Lee"),
    "yacht club": Place(26.5556, -81.9469, "Cape Coral", "Lee"),
    "sun splash": Place(26.6503, -81.9556, "Cape Coral", "Lee"),
    "cape coral-lee county public library": Place(26.6303, -81.9832, "Cape Coral", "Lee"),
    "northwest regional library": Place(26.7147, -82.0060, "Cape Coral", "Lee"),
    "cape coral": Place(26.5629, -81.9495, "Cape Coral", "Lee"),
    # --- Fort Myers -----------------------------------------------------
    "arcade theat": Place(26.6469, -81.8710, "Fort Myers", "Lee"),
    "historic arcade": Place(26.6469, -81.8710, "Fort Myers", "Lee"),
    "artstage studio": Place(26.6469, -81.8710, "Fort Myers", "Lee"),
    "florida repertory": Place(26.6469, -81.8710, "Fort Myers", "Lee"),
    "alliance for the arts": Place(26.5710, -81.8845, "Fort Myers", "Lee"),
    "10091 mcgregor": Place(26.5710, -81.8845, "Fort Myers", "Lee"),
    "sidney": Place(26.6462, -81.8718, "Fort Myers", "Lee"),
    "barbara b. mann": Place(26.5301, -81.8985, "Fort Myers", "Lee"),
    "broadway palm": Place(26.5860, -81.8703, "Fort Myers", "Lee"),
    "2200 second street": Place(26.6446, -81.8723, "Fort Myers", "Lee"),
    "city hall, 2200": Place(26.6446, -81.8723, "Fort Myers", "Lee"),
    "fort myers regional library": Place(26.6438, -81.8697, "Fort Myers", "Lee"),
    "lakes regional library": Place(26.5586, -81.8757, "Fort Myers", "Lee"),
    "edison": Place(26.6360, -81.8720, "Fort Myers", "Lee"),
    "lakes park": Place(26.5364, -81.8797, "Fort Myers", "Lee"),
    "centennial park": Place(26.6455, -81.8748, "Fort Myers", "Lee"),
    "fort myers": Place(26.6406, -81.8723, "Fort Myers", "Lee"),
    # --- rest of Lee ----------------------------------------------------
    "brightwater": Place(26.7355, -81.8420, "North Fort Myers", "Lee"),
    "north fort myers": Place(26.7128, -81.8534, "North Fort Myers", "Lee"),
    "east county regional library": Place(26.6155, -81.6360, "Lehigh Acres", "Lee"),
    "lehigh acres": Place(26.6120, -81.6248, "Lehigh Acres", "Lee"),
    "riverdale public library": Place(26.7093, -81.7396, "Fort Myers", "Lee"),
    "estero": Place(26.4381, -81.8067, "Estero", "Lee"),
    "bonita springs": Place(26.3398, -81.7787, "Bonita Springs", "Lee"),
    "sanibel": Place(26.4478, -82.0106, "Sanibel", "Lee"),
    "captiva": Place(26.5203, -82.1876, "Captiva", "Lee"),
    "pine island": Place(26.6167, -82.1275, "Pine Island", "Lee"),
    "bokeelia": Place(26.7014, -82.1526, "Bokeelia", "Lee"),
    "matlacha": Place(26.6314, -82.0724, "Matlacha", "Lee"),
    "cayo costa": Place(26.6803, -82.2400, "Cayo Costa", "Lee"),
    "cabbage key": Place(26.6584, -82.2231, "Cabbage Key", "Lee"),
    "boca grande": Place(26.7473, -82.2612, "Boca Grande", "Lee"),
    "fort myers beach": Place(26.4523, -81.9481, "Fort Myers Beach", "Lee"),
    "florida gulf coast university": Place(26.4636, -81.7748, "Fort Myers", "Lee"),
    "fgcu": Place(26.4636, -81.7748, "Fort Myers", "Lee"),
    "lee campus": Place(26.5936, -81.8790, "Fort Myers", "Lee"),
    "thomas edison campus": Place(26.5936, -81.8790, "Fort Myers", "Lee"),
    "suncoast credit union arena": Place(26.5936, -81.8790, "Fort Myers", "Lee"),
    # --- Collier / Charlotte --------------------------------------------
    "naples botanical": Place(26.1189, -81.7756, "Naples", "Collier"),
    "gulfshore playhouse": Place(26.1443, -81.7940, "Naples", "Collier"),
    "artis": Place(26.2192, -81.8025, "Naples", "Collier"),
    "naples": Place(26.1420, -81.7948, "Naples", "Collier"),
    "marco island": Place(25.9412, -81.7187, "Marco Island", "Collier"),
    "immokalee": Place(26.4187, -81.4173, "Immokalee", "Collier"),
    "punta gorda": Place(26.9298, -82.0454, "Punta Gorda", "Charlotte"),
    "port charlotte": Place(26.9762, -82.0906, "Port Charlotte", "Charlotte"),
}

_VENUE_KEYS = sorted(VENUES, key=len, reverse=True)

VIRTUAL_RE = re.compile(r"\b(zoom|online|virtual|webinar|teams meeting|livestream)\b", re.I)


def locate(
    location: str | None,
    *,
    source_default: Place | None = None,
) -> dict[str, object]:
    """Place an event. Returns lat/lon/city/county/region/geo_precision.

    Order: virtual → venue substring → source centroid → nothing.
    """
    text = (location or "").strip()
    if text and VIRTUAL_RE.search(text):
        return {
            "lat": None, "lon": None, "city": None, "county": None,
            "region": source_default.region if source_default else None,
            "distance_mi": None, "geo_precision": "virtual",
        }
    low = text.lower()
    if low:
        for key in _VENUE_KEYS:
            if key in low:
                p = VENUES[key]
                # A bare city key is a weaker claim than a named venue.
                precision = "city" if p.city.lower() == key else "venue"
                return {
                    "lat": p.lat, "lon": p.lon, "city": p.city, "county": p.county,
                    "region": p.region, "distance_mi": distance_from_home_mi(p.lat, p.lon),
                    "geo_precision": precision,
                }
    if source_default is not None:
        p = source_default
        return {
            "lat": p.lat, "lon": p.lon, "city": p.city, "county": p.county,
            "region": p.region, "distance_mi": distance_from_home_mi(p.lat, p.lon),
            "geo_precision": "source_default",
        }
    return {
        "lat": None, "lon": None, "city": None, "county": None, "region": None,
        "distance_mi": None, "geo_precision": "none",
    }
