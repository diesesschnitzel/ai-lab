"""Tests for prospecting pipeline GDPR compliance helpers."""

from datetime import datetime, timedelta

from src.apivault.prospecting.gdpr import (
    compute_retention_date,
    determine_legal_basis,
    is_data_expired,
    sanitize_for_gdpr,
    validate_legal_basis,
)


def test_compute_retention_date():
    discovered = datetime(2026, 1, 1)
    retention = compute_retention_date(discovered)
    assert retention == datetime(2027, 1, 1)


def test_compute_retention_date_custom_days():
    discovered = datetime(2026, 1, 1)
    retention = compute_retention_date(discovered, retention_days=30)
    assert retention == datetime(2026, 1, 31)


def test_validate_legal_basis_valid():
    valid = ["consent", "contract", "legal_obligation", "legitimate_interest"]
    for basis in valid:
        assert validate_legal_basis(basis) is True


def test_validate_legal_basis_invalid():
    assert validate_legal_basis("spam") is False
    assert validate_legal_basis(None) is False
    assert validate_legal_basis("") is False


def test_determine_legal_basis_with_consent():
    assert determine_legal_basis("google_maps", has_consent=True) == "consent"


def test_determine_legal_basis_public_source():
    assert determine_legal_basis("google_maps") == "legitimate_interest"
    assert determine_legal_basis("yelp") == "legitimate_interest"
    assert determine_legal_basis("yellow_pages") == "legitimate_interest"
    assert determine_legal_basis("europages") == "legitimate_interest"


def test_determine_legal_basis_unknown_source():
    # Unknown sources still default to legitimate_interest for B2B
    assert determine_legal_basis("unknown_source") == "legitimate_interest"


def test_sanitize_for_gdpr_strips_sensitive():
    data = {
        "name": "Test Company",
        "website": "https://example.com",
        "phone": "+49 30 12345678",
        "personal_notes": "Owner likes coffee",
        "social_security": "123-45-6789",
        "tax_id": "DE123456789",
        "industry": "Restaurant",
    }
    sanitized = sanitize_for_gdpr(data)
    assert "name" in sanitized
    assert "website" in sanitized
    assert "personal_notes" not in sanitized
    assert "social_security" not in sanitized
    assert "tax_id" not in sanitized
    assert "industry" in sanitized


def test_sanitize_for_gdpr_preserves_allowed():
    data = {
        "name": "Test",
        "website": "https://example.com",
        "email": "info@example.com",
        "address": "Berlin",
        "city": "Berlin",
        "country": "DE",
        "industry": "Tech",
        "category": "SaaS",
        "source": "google_maps",
    }
    sanitized = sanitize_for_gdpr(data)
    assert sanitized == data


def test_is_data_expired():
    assert is_data_expired(None) is True
    past = datetime.utcnow() - timedelta(days=400)
    assert is_data_expired(past) is True
    future = datetime.utcnow() + timedelta(days=100)
    assert is_data_expired(future) is False
