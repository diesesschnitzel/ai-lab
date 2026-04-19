"""Tests for the public-apis GitHub scraper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.apivault.scrapers.directories.public_apis_github import (
    SOURCE_URL,
    PublicApisGitHub,
)

SAMPLE_README = """\
# Public APIs

## Animals

| API | Description | Auth | HTTPS | CORS | Link |
|---|---|---|---|---|---|
| Cat Facts | Daily cat facts | No | Yes | No | [catfacts.nightmare.io](https://catfacts.nightmare.io) |
| Dog CEO | Dog breeds | No | Yes | Yes | [dog.ceo](https://dog.ceo) |

## Finance

| API | Description | Auth | HTTPS | CORS | Link |
|---|---|---|---|---|---|
| CoinGecko | Crypto prices | No | Yes | Yes | [coingecko.com](https://www.coingecko.com/en/api) |
"""


class TestPublicApisGitHub:
    @pytest.mark.asyncio
    async def test_name_and_frequency(self):
        scraper = PublicApisGitHub()
        assert scraper.name == "public_apis_github"
        assert scraper.frequency_hours == 6

    @pytest.mark.asyncio
    async def test_parses_categories(self):
        scraper = PublicApisGitHub()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_README
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.public_apis_github.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 3

        cat_facts = candidates[0]
        assert cat_facts.raw_name == "Cat Facts"
        assert cat_facts.raw_json["category"] == "Animals"

        dog_ceo = candidates[1]
        assert dog_ceo.raw_name == "Dog CEO"
        assert dog_ceo.raw_json["category"] == "Animals"

        coingecko = candidates[2]
        assert coingecko.raw_name == "CoinGecko"
        assert coingecko.raw_json["category"] == "Finance"

    @pytest.mark.asyncio
    async def test_parses_auth_type(self):
        scraper = PublicApisGitHub()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_README
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.public_apis_github.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        cat_facts = candidates[0]
        assert cat_facts.raw_auth_type is None

    @pytest.mark.asyncio
    async def test_extracts_base_url(self):
        scraper = PublicApisGitHub()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_README
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.public_apis_github.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        cat_facts = candidates[0]
        assert cat_facts.raw_base_url == "https://catfacts.nightmare.io"
        assert cat_facts.raw_docs_url == "https://catfacts.nightmare.io"

    @pytest.mark.asyncio
    async def test_sets_source_url(self):
        scraper = PublicApisGitHub()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_README
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.public_apis_github.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert all(c.source_url == SOURCE_URL for c in candidates)

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_no_candidates(self):
        scraper = PublicApisGitHub()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.public_apis_github.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_skips_header_and_separator_lines(self):
        scraper = PublicApisGitHub()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_README
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.public_apis_github.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert all(c.raw_name not in ("API", "Description", "Auth") for c in candidates)
