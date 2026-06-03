from swfl_event_scraper.scrape import scrape_source
from swfl_event_scraper.sources import Source, SourceKind


def test_fort_myers_scrape_enriches_civicengage_detail_pages(monkeypatch):
    list_html = """
    <ul>
      <li>
        <a href="/Calendar.aspx?EID=6853&month=6&year=2026&day=3&calType=0">details</a>
        <span itemscope itemtype="http://schema.org/Event">
          <span itemprop="name">SWFL Pride Festival</span>
          <span itemprop="startDate">2026-06-13T14:00:00</span>
        </span>
      </li>
    </ul>
    """
    detail_html = """
    <span itemscope itemtype="http://schema.org/Event">
      <span itemprop="startDate">2026-06-13T14:00:00</span>
      <div itemprop="description" class="fr-view">
        The free street festival is open to everyone.
      </div>
    </span>
    """

    def fake_fetch_text(url):
        if "EID=6853" in url:
            return detail_html
        return list_html

    monkeypatch.setattr("swfl_event_scraper.scrape.fetch_text", fake_fetch_text)

    events, error = scrape_source(
        Source(
            name="Fort Myers CivicEngage Calendar",
            url="https://fortmyers.gov/calendar.aspx",
            kind=SourceKind.CIVIC_GOV,
            parser="fort_myers_civicengage",
        )
    )

    assert error is None
    assert len(events) == 1
    assert events[0].description == "The free street festival is open to everyone."
    assert events[0].price_text == "Free"
    assert events[0].payment_required is False
    assert events[0].registration_required is False
    assert events[0].access_type == "drop_in"
    assert events[0].joinability == "drop_in_ok"
