"""ScraperRun model — audit log of every scraper execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.apivault.models.base import Base


class ScraperRun(Base):
    """Audit log. One row per scraper execution, regardless of outcome."""

    __tablename__ = "scraper_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        server_default=text("uuid_generate_v4()"),
        primary_key=True,
    )
    scraper_name: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # type: ignore[arg-type]
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'running'"),
    )
    candidates_found: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    candidates_new: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    candidates_updated: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_scraper_runs_name", "scraper_name"),
        Index("idx_scraper_runs_started", "started_at", postgresql_ops={"started_at": "DESC"}),
        Index("idx_scraper_runs_status", "status"),
    )
