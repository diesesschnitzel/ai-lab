"""ApiHealthLog model — time-series history of every validation probe."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.apivault.models.base import Base


class ApiHealthLog(Base):
    __tablename__ = "api_health_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        server_default=text("uuid_generate_v4()"),
        primary_key=True,
    )
    api_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # type: ignore[arg-type]
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    dns_resolves: Mapped[bool | None] = mapped_column(Boolean)
    ssl_valid: Mapped[bool | None] = mapped_column(Boolean)
    auth_type_detected: Mapped[str | None] = mapped_column(Text)
    rate_limit_detected: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    checker_version: Mapped[str | None] = mapped_column(Text)

    api: Mapped["Api"] = relationship(  # noqa: UP037, F821
        "Api", back_populates="health_logs"
    )

    __table_args__ = (
        ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        Index("idx_health_log_api_id", "api_id", "checked_at", postgresql_ops={"checked_at": "DESC"}),
        Index("idx_health_log_checked", "checked_at", postgresql_ops={"checked_at": "DESC"}),
        Index(
            "idx_health_log_status",
            "status",
            "checked_at",
            postgresql_ops={"checked_at": "DESC"},
        ),
    )
