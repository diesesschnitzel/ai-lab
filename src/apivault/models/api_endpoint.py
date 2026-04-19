"""ApiEndpoint model — individual endpoint records parsed from specs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.apivault.models.base import Base


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        server_default=text("uuid_generate_v4()"),
        primary_key=True,
    )
    api_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    responses: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    auth_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    example_request: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    example_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    deprecated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # type: ignore[arg-type]
        nullable=False,
    )

    api: Mapped["Api"] = relationship(  # noqa: UP037, F821
        "Api", back_populates="endpoints"
    )

    __table_args__ = (
        ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        Index("idx_endpoints_api_id", "api_id"),
        Index("idx_endpoints_method", "method"),
        Index(
            "idx_endpoints_deprecated",
            "deprecated",
            postgresql_where=text("deprecated = false"),
        ),
        Index("idx_endpoints_unique", "api_id", "method", "path", unique=True),
    )
