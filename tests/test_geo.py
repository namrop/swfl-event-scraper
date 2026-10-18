import pytest

from swfl_event_scraper.geo import Place, VENUES, distance_from_home_mi, locate


STREET_SUFFIXES = (
    "Road", "Rd", "Blvd", "Boulevard", "Parkway", "Pkwy", "Avenue", "Ave",
    "Street", "St", "Drive", "Dr", "Lane", "Ln", "Way", "Court", "Ct",
    "Highway", "Hwy", "Trail", "Terrace", "Circle",
)

# These keys include a street number, not just a place name.
ADDRESS_KEYS = {
    "1015 cultural park", "815 nicholas", "10091 mcgregor",
    "2200 second street", "city hall, 2200",
}


def assert_place(result, key, precision):
    place = VENUES[key]
    assert result == {
        "lat": place.lat,
        "lon": place.lon,
        "city": place.city,
        "county": place.county,
        "region": place.region,
        "distance_mi": distance_from_home_mi(place.lat, place.lon),
        "geo_precision": precision,
    }


@pytest.mark.parametrize("location", [
    "Farmer Joe's, 1401 SW Pine Island Road, Cape Coral",
    "Cape Coral Bootstrap Homeless Ministry inside the Messiah Lutheran Church, "
    "2691 N.E. Pine Island Road, Cape Coral",
    "Target 2316, 1890 NE Pine Island Rd, Cape Coral",
])
def test_observed_pine_island_road_events_are_in_cape_coral(location):
    assert_place(locate(location), "cape coral", "city")


@pytest.mark.parametrize(("location", "city_key"), [
    ("Community center, 100 Pine Island Road, North Fort Myers", "north fort myers"),
    ("Community center, 100 Immokalee Road, Naples", "naples"),
    ("Community center, 100 Estero Blvd, Fort Myers Beach", "fort myers beach"),
    ("Community center, 100 Estero Parkway, Fort Myers", "fort myers"),
    ("Community center, 100 Sanibel-Captiva Road, Sanibel", "sanibel"),
    ("Community center, 100 Bonita Beach Road, Bonita Springs", "bonita springs"),
    ("Community center, 100 Cape Coral Parkway, Fort Myers", "fort myers"),
    ("Community center, 100 Edison Avenue, Cape Coral", "cape coral"),
    ("Community center, 100 Sidney Street, Cape Coral", "cape coral"),
    ("Community center, 100 Brightwater Court, Cape Coral", "cape coral"),
])
def test_street_name_does_not_override_the_city(location, city_key):
    assert_place(locate(location), city_key, "city")


@pytest.mark.parametrize("key", VENUES)
def test_every_table_key_distinguishes_place_names_from_numbered_addresses(key):
    # Synthetic addresses audit all keys, including city names nested inside
    # longer venue names. They do not assert these streets actually exist.
    result = locate(f"Community center, 123 {key} Road")
    if key in ADDRESS_KEYS:
        assert_place(result, key, "venue")
        return
    assert result["geo_precision"] == "none"
    assert result["city"] is None


@pytest.mark.parametrize("suffix", STREET_SUFFIXES)
@pytest.mark.parametrize("period", ["", "."])
def test_street_suffixes_are_case_insensitive_and_allow_a_period(suffix, period):
    result = locate(f"Community center, 123 pInE iSlAnD {suffix.swapcase()}{period}")
    assert result["geo_precision"] == "none"
    assert result["city"] is None


@pytest.mark.parametrize("street", [
    "Sanibel-Captiva Road", "Sanibel - Captiva Rd.", "Sanibel–Captiva Road",
    "Estero Blvd", "Immokalee Road", "Bonita Beach Road",
])
def test_street_without_a_city_does_not_invent_one(street):
    assert locate(f"Community center, 123 {street}")["geo_precision"] == "none"


@pytest.mark.parametrize(("location", "city_key"), [
    ("Pine Island community group, Cape Coral", "cape coral"),
    ("Sanibel community group, Naples", "naples"),
    ("Immokalee community group, 100 Main Road, nApLeS  ", "naples"),
])
def test_final_known_city_beats_other_city_mentions(location, city_key):
    assert_place(locate(location), city_key, "city")


@pytest.mark.parametrize(("location", "city_key"), [
    ("Community meeting, Pine Island", "pine island"),
    ("Matlacha Community Park, Matlacha", "matlacha"),
    ("Island market, Bokeelia", "bokeelia"),
    ("Community center, 123 Pine Island Road, Pine Island", "pine island"),
])
def test_genuine_island_locations_remain_on_the_island(location, city_key):
    assert_place(locate(location), city_key, "city")


@pytest.mark.parametrize(("location", "key"), [
    ("Cultural Park Theatre, 1015 Cultural Park Blvd., Cape Coral", "cultural park theat"),
    ("Rotary Park, 5505 Rose Garden Road, Cape Coral", "rotary park"),
    ("Arcade Theatre, 2268 Bay Street, Fort Myers", "arcade theat"),
    ("Cape Coral-Lee County Public Library, Cape Coral", "cape coral-lee county public library"),
    ("Cultural Park Theatre, 100 Pine Island Road, North Fort Myers", "cultural park theat"),
    ("Lee Campus - Basketball Court", "lee campus"),
])
def test_named_venues_keep_priority_over_city_and_street_matches(location, key):
    assert_place(locate(location), key, "venue")


@pytest.mark.parametrize(("location", "key"), [
    ("1015 Cultural Park Blvd., Cape Coral", "cultural park blvd"),
    ("1015 Cultural Park Boulevard, Cape Coral", "cultural park boulevard"),
    ("815 Nicholas Parkway, Cape Coral", "815 nicholas"),
    ("10091 McGregor Boulevard, Fort Myers", "10091 mcgregor"),
    ("City Hall, 2200 Second Street, Fort Myers", "2200 second street"),
])
def test_deliberate_address_anchors_keep_venue_precision(location, key):
    assert_place(locate(location), key, "venue")


@pytest.mark.parametrize("location", [
    None, "", "Unlisted community center", "Community center, 123 Pine Island Road",
])
def test_source_default_is_used_when_no_place_can_be_matched(location):
    default = Place(26.6294, -81.9860, "", "Lee", "custom region")
    assert locate(location, source_default=default) == {
        "lat": default.lat,
        "lon": default.lon,
        "city": "",
        "county": "Lee",
        "region": "custom region",
        "distance_mi": distance_from_home_mi(default.lat, default.lon),
        "geo_precision": "source_default",
    }


@pytest.mark.parametrize("virtual", [
    "Zoom", "online", "virtual", "webinar", "Teams meeting", "livestream",
])
def test_virtual_path_keeps_priority_and_source_region(virtual):
    default = Place(26.6294, -81.9860, "", "Lee", "custom region")
    assert locate(f"{virtual}, 123 Pine Island Road, Cape Coral", source_default=default) == {
        "lat": None,
        "lon": None,
        "city": None,
        "county": None,
        "region": "custom region",
        "distance_mi": None,
        "geo_precision": "virtual",
    }


def test_no_place_or_default_leaves_all_geography_unknown():
    assert locate(None) == {
        "lat": None, "lon": None, "city": None, "county": None, "region": None,
        "distance_mi": None, "geo_precision": "none",
    }


def test_city_without_a_comma_keeps_existing_longest_match():
    assert_place(locate("Community gathering in North Fort Myers"), "north fort myers", "city")


def test_final_city_does_not_promote_a_previously_losing_venue_match():
    assert_place(locate("Brightwater Lagoon, North Fort Myers"), "north fort myers", "city")


def test_suffix_must_be_a_whole_word():
    assert_place(locate("Pine Island Roadhouse"), "pine island", "city")


def test_known_distance_from_home_is_unchanged():
    assert locate("Pine Island")["distance_mi"] == 11.61
    assert locate("Cape Coral")["distance_mi"] == 0.0
