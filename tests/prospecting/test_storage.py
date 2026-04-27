"""Tests for prospecting pipeline storage layer."""

from datetime import datetime, timedelta
import uuid

from src.apivault.prospecting.models import (
    Prospect,
    ProspectSource,
    SEOAssessment,
    WebsiteAnalysis,
)
from src.apivault.prospecting.storage import ProspectStore, get_store, reset_store


def make_prospect(**overrides) -> Prospect:
    defaults = {
        "name": f"Test Business {uuid.uuid4().hex[:6]}",
        "website": "https://example.com",
        "source": ProspectSource.GOOGLE_MAPS,
    }
    defaults.update(overrides)
    return Prospect(**defaults)


def test_add_prospect():
    store = ProspectStore()
    p = make_prospect(name="Test Cafe")
    pid = store.add_prospect(p)
    assert pid == "Test Cafe"
    assert store.count() == 1
    assert store.get_prospect("Test Cafe") is not None


def test_add_prospect_sets_gdpr_fields():
    store = ProspectStore()
    p = make_prospect(name="GDPR Test")
    store.add_prospect(p)
    stored = store.get_prospect("GDPR Test")
    assert stored.gdpr_legal_basis == "legitimate_interest"
    assert stored.gdpr_data_retained_until is not None


def test_duplicate_prospect_by_website():
    store = ProspectStore()
    p1 = make_prospect(name="Cafe A", website="https://cafe.de")
    p2 = make_prospect(name="Cafe B", website="https://cafe.de")

    store.add_prospect(p1)
    pid = store.add_prospect(p2)
    assert pid == "Cafe A"  # Returns existing
    assert store.count() == 1


def test_add_analysis():
    store = ProspectStore()
    p = make_prospect(name="Analysis Test")
    store.add_prospect(p)

    analysis = WebsiteAnalysis(prospect_id="Analysis Test")
    store.add_analysis("Analysis Test", analysis)
    assert store.get_analysis("Analysis Test") is analysis


def test_list_prospects():
    store = ProspectStore()
    store.add_prospect(make_prospect(name="A", website="https://a.com", source=ProspectSource.GOOGLE_MAPS))
    store.add_prospect(make_prospect(name="B", website="https://b.com", source=ProspectSource.YELP))
    store.add_prospect(make_prospect(name="C", website="https://c.com", source=ProspectSource.GOOGLE_MAPS))

    all_prospects = store.list_prospects()
    assert len(all_prospects) == 3

    google = store.list_prospects(source="google_maps")
    assert len(google) == 2

    yelp = store.list_prospects(source="yelp")
    assert len(yelp) == 1


def test_list_prospects_with_limit():
    store = ProspectStore()
    for i in range(10):
        store.add_prospect(make_prospect(name=f"Business {i}", website=f"https://business{i}.com"))

    limited = store.list_prospects(limit=3)
    assert len(limited) == 3

    offset = store.list_prospects(limit=3, offset=5)
    assert len(offset) == 3


def test_delete_expired():
    store = ProspectStore()
    p = make_prospect(name="Expired")
    store.add_prospect(p)
    stored = store.get_prospect("Expired")
    # Manually set retention date to past
    stored.gdpr_data_retained_until = datetime.utcnow() - timedelta(days=10)

    deleted = store.delete_expired()
    assert deleted == 1
    assert store.count() == 0


def test_delete_not_expired():
    store = ProspectStore()
    p = make_prospect(name="Valid")
    store.add_prospect(p)

    deleted = store.delete_expired()
    assert deleted == 0
    assert store.count() == 1


def test_handle_deletion_request():
    store = ProspectStore()
    p = make_prospect(name="Delete Me")
    store.add_prospect(p)

    result = store.handle_deletion_request("Delete Me")
    assert result is True
    assert store.count() == 0


def test_handle_deletion_request_not_found():
    store = ProspectStore()
    result = store.handle_deletion_request("Nonexistent")
    assert result is False


def test_get_store_singleton():
    reset_store()
    s1 = get_store()
    s2 = get_store()
    assert s1 is s2
    reset_store()
