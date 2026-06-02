from swfl_event_scraper.sources import SOURCES, SourceKind


def test_civic_sources_are_first_class_not_eventbrite_only():
    names = {source.name for source in SOURCES}

    assert "Cape Coral City Calendar" in names
    assert "Cape Coral Parks WebTrac Events" in names
    assert "Lee County Parks & Recreation Events" in names
    assert "Lee County Library System Events" in names
    assert "Fort Myers CivicEngage Calendar" in names


def test_sources_include_civic_kind_for_government_pages():
    civic = [source for source in SOURCES if source.kind is SourceKind.CIVIC_GOV]

    assert len(civic) >= 4
    assert all(source.url.startswith("https://") for source in civic)
