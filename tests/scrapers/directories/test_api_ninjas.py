"""Tests for the API Ninjas scraper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.apivault.scrapers.directories.api_ninjas import (
    BASE_API_URL,
    SOURCE_URL,
    ApiNinjas,
)

SAMPLE_HTML = """\
<html>
<body>
  <div class="api-list">
    <div class="api-item">
      <a href="/api/commodityprice">Commodity Price</a>
      <p>Real-time prices for commodities</p>
    </div>
    <div class="api-item">
      <a href="/api/nutrition">Nutrition</a>
      <p>Nutrition facts for foods</p>
    </div>
    <div class="api-item">
      <a href="/api/whois">WHOIS</a>
      <p>Domain registry lookup</p>
    </div>
  </div>
</body>
</html>
"""


class TestApiNinjas:
    @pytest.mark.asyncio
    async def test_name_and_frequency(self):
        scraper = ApiNinjas()
        assert scraper.name == "api_ninjas"
        assert scraper.frequency_hours == 24

    @pytest.mark.asyncio
    async def test_parses_api_entries(self):
        scraper = ApiNinjas()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 3

    @pytest.mark.asyncio
    async def test_extracts_api_name(self):
        scraper = ApiNinjas()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        names = {c.raw_name for c in candidates}
        assert "Commodity Price" in names
        assert "Nutrition" in names
        assert "WHOIS" in names

    @pytest.mark.asyncio
    async def test_extracts_description(self):
        scraper = ApiNinjas()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        commodity = next(c for c in candidates if c.raw_name == "Commodity Price")
        assert commodity.raw_description == "Real-time prices for commodities"

    @pytest.mark.asyncio
    async def test_constructs_api_url(self):
        scraper = ApiNinjas()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        commodity = next(c for c in candidates if c.raw_name == "Commodity Price")
        assert commodity.raw_base_url == f"{BASE_API_URL}/commodityprice"

    @pytest.mark.asyncio
    async def test_constructs_docs_url(self):
        scraper = ApiNinjas()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        commodity = next(c for c in candidates if c.raw_name == "Commodity Price")
        assert commodity.raw_docs_url == f"{SOURCE_URL}/api/commodityprice"

    @pytest.mark.asyncio
    async def test_sets_auth_type_apikey(self):
        scraper = ApiNinjas()

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert all(c.raw_auth_type == "apikey" for c in candidates)

    @pytest.mark.asyncio
    async def test_deduplicates_apis(self):
        scraper = ApiNinjas()

        duplicate_html = """\
        <html>
        <body>
          <a href="/api/nutrition">Nutrition</a>
          <a href="/api/nutrition">Nutrition</a>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = duplicate_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 1

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_no_candidates(self):
        scraper = ApiNinjas()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.apivault.scrapers.directories.api_ninjas.make_client",
            return_value=mock_client,
        ):
            candidates = [c async for c in scraper.run()]

        assert len(candidates) == 0
