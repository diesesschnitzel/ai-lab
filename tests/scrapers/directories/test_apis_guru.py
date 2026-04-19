"""Tests for the apis.guru scraper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.apivault.scrapers.directories.apis_guru import SOURCE_URL, ApisGuru

SAMPLE_DATA = {
    "amazonaws.com": {
        "info": {
            "title": "Amazon Web Services",
            "description": "AWS API",
            "x-apisguru-categories": ["cloud"],
        },
        "externalDocs": {"url": "https://docs.aws.amazon.com/"},
        "preferred": "latest",
        "versions": {
            "latest": {
                "swaggerUrl": "https://api.example.com/aws/swagger.json",
                "openAPIUrl": "https://api.example.com/aws/openapi.json",
            }
        },
    },
    "github.com": {
        "info": {
            "title": "GitHub",
            "description": "GitHub REST API",
            "x-apisguru-categories": ["development"],
        },
        "externalDocs": {"url": "https://docs.github.com/"},
        "versions": {
            "v3": {
                "swaggerUrl": "https://api.example.com/github/swagger.json",
                "openAPIUrl": "https://api.example.com/github/openapi.json",
            }
        },
    },
}


class TestApisGuru:
    @pytest.mark.asyncio
    async def test_name_and_frequency(self):
        scraper = ApisGuru()
        assert scraper.name == "apis_guru"
        assert scraper.frequency_hours == 6

    @pytest.mark.asyncio
    async def test_parses_api_entries(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 2

    @pytest.mark.asyncio
    async def test_extracts_title_and_description(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        aws = next(c for c in candidates if c.raw_json["api_name"] == "amazonaws.com")
        assert aws.raw_name == "Amazon Web Services"
        assert aws.raw_description == "AWS API"

    @pytest.mark.asyncio
    async def test_extracts_docs_url(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        aws = next(c for c in candidates if c.raw_json["api_name"] == "amazonaws.com")
        assert aws.raw_docs_url == "https://docs.aws.amazon.com/"

    @pytest.mark.asyncio
    async def test_extracts_base_url_from_swagger_url(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        aws = next(c for c in candidates if c.raw_json["api_name"] == "amazonaws.com")
        assert aws.raw_base_url == "https://api.example.com/aws"

    @pytest.mark.asyncio
    async def test_uses_preferred_version(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        aws = next(c for c in candidates if c.raw_json["api_name"] == "amazonaws.com")
        assert aws.raw_json["swagger_url"] == "https://api.example.com/aws/swagger.json"

    @pytest.mark.asyncio
    async def test_falls_back_to_latest_version(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        github = next(c for c in candidates if c.raw_json["api_name"] == "github.com")
        assert github.raw_json["swagger_url"] == "https://api.example.com/github/swagger.json"

    @pytest.mark.asyncio
    async def test_includes_categories(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        aws = next(c for c in candidates if c.raw_json["api_name"] == "amazonaws.com")
        assert aws.raw_json["categories"] == ["cloud"]

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_no_candidates(self):
        scraper = ApisGuru()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_sets_source_url(self):
        scraper = ApisGuru()

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=SAMPLE_DATA)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.apis_guru.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert all(c.source_url == SOURCE_URL for c in candidates)
