"""Api model — the primary store for all discovered APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.apivault.models.base import Base, TimestampMixin


class Api(Base, TimestampMixin):
    __tablename__ = "apis"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        server_default=text("uuid_generate_v4()"),
        primary_key=True,
    )
    slug: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    description: Mapped[str | None] = mapped_column(Text)
    description_llm: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(Text)

    base_url: Mapped[str | None] = mapped_column(Text)
    docs_url: Mapped[str | None] = mapped_column(Text)
    spec_url: Mapped[str | None] = mapped_column(Text)
    postman_url: Mapped[str | None] = mapped_column(Text)
    signup_url: Mapped[str | None] = mapped_column(Text)

    auth_type: Mapped[str] = mapped_column(
        Text,
        server_default=text("'unknown'"),
    )
    auth_notes: Mapped[str | None] = mapped_column(Text)
    signup_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    login_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    free_tier: Mapped[str | None] = mapped_column(Text)
    rate_limit: Mapped[str | None] = mapped_column(Text)
    rate_limit_header: Mapped[str | None] = mapped_column(Text)
    pricing_url: Mapped[str | None] = mapped_column(Text)

    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    use_cases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    formats: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    protocols: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    data_formats: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    openapi_version: Mapped[str | None] = mapped_column(Text)

    country: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)

    company: Mapped[str | None] = mapped_column(Text)
    company_url: Mapped[str | None] = mapped_column(Text)

    source_names: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    source_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # type: ignore[arg-type]
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    health_score: Mapped[int | None] = mapped_column(Integer)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    ssl_valid: Mapped[bool | None] = mapped_column(Boolean)
    ssl_expiry: Mapped[date | None] = mapped_column(Date)
    dns_resolves: Mapped[bool | None] = mapped_column(Boolean)
    consecutive_failures: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding_model: Mapped[str | None] = mapped_column(Text)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    fts: Mapped[Any | None] = mapped_column(TSVECTOR)

    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    endpoints: Mapped[list["ApiEndpoint"]] = relationship(  # noqa: UP037, F821
        "ApiEndpoint", back_populates="api", cascade="all, delete-orphan"
    )
    health_logs: Mapped[list["ApiHealthLog"]] = relationship(  # noqa: UP037, F821
        "ApiHealthLog", back_populates="api", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("health_score BETWEEN 0 AND 100", name="chk_health_score_range"),
        CheckConstraint(
            "status IN ('unknown','pending_validation','active','degraded','dead')",
            name="chk_api_status",
        ),
        CheckConstraint(
            "auth_type IN ('none','apikey','oauth2','basic','bearer','unknown')",
            name="chk_auth_type",
        ),
        Index("idx_apis_slug", "slug", unique=True, postgresql_where=text("slug IS NOT NULL")),
        Index("idx_apis_base_url", "base_url", postgresql_where=text("base_url IS NOT NULL")),
        Index("idx_apis_status", "status"),
        Index("idx_apis_auth_type", "auth_type"),
        Index("idx_apis_health_score", "health_score", postgresql_ops={"health_score": "DESC"}),
        Index("idx_apis_last_checked", "last_checked"),
        Index("idx_apis_country", "country", postgresql_where=text("country IS NOT NULL")),
        Index("idx_apis_categories", "categories", postgresql_using="gin"),
        Index("idx_apis_tags", "tags", postgresql_using="gin"),
        Index("idx_apis_formats", "formats", postgresql_using="gin"),
        Index("idx_apis_source_names", "source_names", postgresql_using="gin"),
        Index("idx_apis_fts", "fts", postgresql_using="gin"),
        Index("idx_apis_status_auth", "status", "auth_type"),
        Index(
            "idx_apis_status_score",
            "status",
            "health_score",
            postgresql_ops={"health_score": "DESC"},
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "idx_apis_pending_validation",
            "created_at",
            postgresql_where=text("status = 'pending_validation'"),
        ),
        Index(
            "idx_apis_pending_enrichment",
            "created_at",
            postgresql_where=text("enriched_at IS NULL AND status != 'dead'"),
        ),
    )
