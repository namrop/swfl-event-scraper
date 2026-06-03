from swfl_event_scraper.models import Event, infer_access_metadata
from swfl_event_scraper.parsers import enrich_event_from_civicengage_detail


def test_public_meeting_metadata_is_free_and_open_to_public_attendance():
    metadata = infer_access_metadata(
        title="City Council Meeting",
        description="The City Council will meet in Council Chambers. Agenda available online.",
        category="Public Meetings",
        source_name="Cape Coral City Calendar",
    )

    assert metadata["price_text"] == "Free"
    assert metadata["payment_required"] is False
    assert metadata["registration_required"] is False
    assert metadata["access_type"] == "public_meeting"
    assert metadata["joinability"] == "public_attendance_ok"


def test_free_open_festival_is_not_misclassified_as_class_series_from_dance_text():
    metadata = infer_access_metadata(
        title="SWFL Pride Festival",
        description=(
            "The free street festival is open to everyone. Above the festival there "
            "will be a rooftop dance party with VIP tickets available."
        ),
        category="City calendar",
    )

    assert metadata["price_text"] == "Free"
    assert metadata["payment_required"] is False
    assert metadata["registration_required"] is False
    assert metadata["access_type"] == "drop_in"
    assert metadata["joinability"] == "drop_in_ok"


def test_vendor_signup_and_parking_cost_do_not_create_attendee_registration_or_event_price():
    metadata = infer_access_metadata(
        title="Fort Myers Farmers Market - Every Saturday!",
        description="For details and to sign up as a vendor, visit the Local Roots website. On-street parking is free.",
        category="City calendar",
    )

    assert metadata["price_text"] is None
    assert metadata["payment_required"] is None
    assert metadata["registration_required"] is False
    assert metadata["access_type"] == "drop_in"
    assert metadata["joinability"] == "drop_in_ok"


def test_food_or_concession_prices_do_not_become_event_admission_price():
    metadata = infer_access_metadata(
        title="Celebrate Flag Day",
        description="Join us for patriotic fun, summer golf, and $2.50 hot dogs.",
        category="City calendar",
    )

    assert metadata["price_text"] is None
    assert metadata["payment_required"] is None


def test_free_movie_without_registration_is_drop_in():
    metadata = infer_access_metadata(
        title="Palm City Cinema presents How to Train Your Dragon",
        description="The free movie will start at 6pm. Feel free to bring a blanket, snacks and drinks.",
        category="City calendar",
    )

    assert metadata["price_text"] == "Free"
    assert metadata["payment_required"] is False
    assert metadata["registration_required"] is False
    assert metadata["access_type"] == "drop_in"
    assert metadata["joinability"] == "drop_in_ok"


def test_reserve_your_spot_and_given_upon_registration_require_registration():
    metadata = infer_access_metadata(
        title="Full Moon Paddle at Four Mile Cove Ecological Preserve",
        description=(
            "The meeting location will be given upon registration. The cost is $40 for "
            "single kayaks and $80 for tandem kayaks. To reserve your spot, call the office."
        ),
        category="Events",
    )

    assert metadata["price_text"] == "$40-$80"
    assert metadata["payment_required"] is True
    assert metadata["registration_required"] is True
    assert metadata["access_type"] == "registration_required"
    assert metadata["joinability"] == "registration_needed"


def test_civicengage_detail_description_enriches_access_metadata():
    event = Event(
        title="SWFL Pride Festival",
        start_datetime="2026-06-13T14:00",
        source_url="https://fortmyers.gov/Calendar.aspx?EID=6853",
        source_name="Fort Myers CivicEngage Calendar",
        category="City calendar",
    )
    html = """
    <span itemscope itemtype="http://schema.org/Event">
      <span itemprop="startDate">2026-06-13T14:00:00</span>
      <div itemprop="description" class="fr-view">
        Please come to the SWFL Pride Festival. The free street festival is open to everyone.
      </div>
    </span>
    """

    enriched = enrich_event_from_civicengage_detail(event, html)

    assert enriched.description == "Please come to the SWFL Pride Festival. The free street festival is open to everyone."
    assert enriched.price_text == "Free"
    assert enriched.payment_required is False
    assert enriched.registration_required is False
    assert enriched.access_type == "drop_in"
    assert enriched.joinability == "drop_in_ok"
