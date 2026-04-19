"""RawCandidate model — landing zone for all scraper output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.apivault.models.base import Base


class RawCandidate(Base):
    """Landing zone for all scraper output. Records here have not yet been
    deduplicated or validated. Treated as a queue.
    """

    __tablename__ = "raw_candidates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        server_default=text("uuid_generate_v4()"),
        primary_key=True,
    )
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_name: Mapped[str | None] = mapped_column(Text)
    raw_description: Mapped[str | None] = mapped_column(Text)
    raw_base_url: Mapped[str | None] = mapped_column(Text)
    raw_docs_url: Mapped[str | None] = mapped_column(Text)
    raw_auth_type: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    error: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # type: ignore[arg-type]
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    apis_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))

    __table_args__ = (
        Index("idx_raw_candidates_status", "status"),
        Index("idx_raw_candidates_source", "source_name"),
        Index("idx_raw_candidates_discovered", "discovered_at"),
        Index("idx_raw_candidates_url", "raw_base_url", postgresql_where=text("raw_base_url IS NOT NULL")),
    )
