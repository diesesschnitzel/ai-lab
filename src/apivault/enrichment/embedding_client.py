"""Embedding clients for generating vector representations of APIs."""

from __future__ import annotations

import asyncio
import logging

import httpx

from src.apivault.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536


class OllamaEmbeddingClient:
    """Generate embeddings using local Ollama (nomic-embed-text)."""

    BASE_URL: str = "http://localhost:11434"
    MODEL: str = "nomic-embed-text"

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_embedding_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding for a single text."""
        if not text.strip():
            return None

        client = await self._get_client()
        try:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            response.raise_for_status()
            embedding = response.json().get("embedding", [])
            return self._pad_embedding(embedding)
        except Exception:
            logger.exception("Ollama embedding failed")
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts in parallel."""
        return await asyncio.gather(*[self.embed(t) for t in texts])

    def _pad_embedding(self, embedding: list[float]) -> list[float]:
        """Pad Ollama embedding (768 dims) to 1536 dims for pgvector compatibility."""
        if len(embedding) >= EMBEDDING_DIM:
            return embedding[:EMBEDDING_DIM]
        return embedding + [0.0] * (EMBEDDING_DIM - len(embedding))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


class OpenAIEmbeddingClient:
    """Generate embeddings using OpenAI text-embedding-3-small."""

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_embedding_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding for a single text."""
        if not text.strip():
            return None

        client = await self._get_client()
        try:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                json={
                    "model": self.model,
                    "input": text,
                    "dimensions": EMBEDDING_DIM,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception:
            logger.exception("OpenAI embedding failed")
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts.

        OpenAI supports batch embedding with multiple inputs in one call.
        """
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            return [None] * len(texts)

        client = await self._get_client()
        try:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                json={
                    "model": self.model,
                    "input": [t for _, t in non_empty],
                    "dimensions": EMBEDDING_DIM,
                },
            )
            response.raise_for_status()
            data = response.json()
            embeddings_map = {i: entry["embedding"] for entry, (i, _) in zip(data["data"], non_empty, strict=False)}
            return [embeddings_map.get(i) for i in range(len(texts))]
        except Exception:
            logger.exception("OpenAI batch embedding failed")
            return [None] * len(texts)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


def get_embedding_client() -> OllamaEmbeddingClient | OpenAIEmbeddingClient | None:
    """Get the appropriate embedding client based on configuration."""
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            logger.warning("OpenAI embedding selected but no API key configured")
            return None
        return OpenAIEmbeddingClient()
    elif settings.embedding_provider == "ollama":
        return OllamaEmbeddingClient()
    else:
        return None
