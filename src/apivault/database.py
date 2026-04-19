"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apivault.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_max,
    min_size=settings.database_pool_min,
    pool_timeout=settings.database_pool_timeout,
    pool_pre_ping=True,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, Any]:
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session_direct() -> AsyncSession:
    """Return a new async session (caller must close)."""
    return async_session_factory()
