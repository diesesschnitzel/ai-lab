"""create initial tables with pgvector support

Revision ID: dd8d9620c6a8
Revises:
Create Date: 2026-04-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "dd8d9620c6a8"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    op.create_table(
        "apis",
        sa.Column("id", sa.Uuid(as_uuid=False), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("slug", sa.Text, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("description_llm", sa.Text),
        sa.Column("version", sa.Text),
        sa.Column("base_url", sa.Text),
        sa.Column("docs_url", sa.Text),
        sa.Column("spec_url", sa.Text),
        sa.Column("postman_url", sa.Text),
        sa.Column("signup_url", sa.Text),
        sa.Column("auth_type", sa.Text, server_default=sa.text("'unknown'")),
        sa.Column("auth_notes", sa.Text),
        sa.Column("signup_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("login_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("free_tier", sa.Text),
        sa.Column("rate_limit", sa.Text),
        sa.Column("rate_limit_header", sa.Text),
        sa.Column("pricing_url", sa.Text),
        sa.Column("categories", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("tags", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("use_cases", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("formats", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("protocols", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("data_formats", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("openapi_version", sa.Text),
        sa.Column("country", sa.Text),
        sa.Column("language", sa.Text),
        sa.Column("company", sa.Text),
        sa.Column("company_url", sa.Text),
        sa.Column("source_names", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("source_urls", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.Text, server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("health_score", sa.Integer),
        sa.Column("last_checked", sa.DateTime(timezone=True)),
        sa.Column("http_status", sa.Integer),
        sa.Column("response_time_ms", sa.Integer),
        sa.Column("ssl_valid", sa.Boolean),
        sa.Column("ssl_expiry", sa.Date),
        sa.Column("dns_resolves", sa.Boolean),
        sa.Column("consecutive_failures", sa.Integer, server_default=sa.text("0")),
        sa.Column("enriched_at", sa.DateTime(timezone=True)),
        sa.Column("embedding_model", sa.Text),
        sa.Column("embedding", sa.dialects.postgresql.VECTOR(1536)),
        sa.Column("fts", sa.dialects.postgresql.TSVECTOR),
        sa.Column("raw_json", sa.dialects.postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("idx_apis_slug", "apis", ["slug"], unique=True, postgresql_where=sa.text("slug IS NOT NULL"))
    op.create_index("idx_apis_base_url", "apis", ["base_url"], postgresql_where=sa.text("base_url IS NOT NULL"))
    op.create_index("idx_apis_status", "apis", ["status"])
    op.create_index("idx_apis_auth_type", "apis", ["auth_type"])
    op.create_index("idx_apis_health_score", "apis", ["health_score"], postgresql_ops={"health_score": "DESC"})
    op.create_index("idx_apis_last_checked", "apis", ["last_checked"])
    op.create_index("idx_apis_country", "apis", ["country"], postgresql_where=sa.text("country IS NOT NULL"))
    op.create_index("idx_apis_categories", "apis", ["categories"], postgresql_using="gin")
    op.create_index("idx_apis_tags", "apis", ["tags"], postgresql_using="gin")
    op.create_index("idx_apis_formats", "apis", ["formats"], postgresql_using="gin")
    op.create_index("idx_apis_source_names", "apis", ["source_names"], postgresql_using="gin")
    op.create_index("idx_apis_fts", "apis", ["fts"], postgresql_using="gin")
    op.create_index("idx_apis_status_auth", "apis", ["status", "auth_type"])
    op.create_index(
        "idx_apis_status_score",
        "apis",
        ["status", "health_score"],
        postgresql_ops={"health_score": "DESC"},
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_apis_pending_validation",
        "apis",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending_validation'"),
    )
    op.create_index(
        "idx_apis_pending_enrichment",
        "apis",
        ["created_at"],
        postgresql_where=sa.text("enriched_at IS NULL AND status != 'dead'"),
    )

    op.execute(
        sa.text("""
        CREATE OR REPLACE FUNCTION apis_fts_update() RETURNS trigger AS $$
        BEGIN
            NEW.fts :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description_llm, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(array_to_string(NEW.tags, ' '), '')), 'C') ||
                setweight(to_tsvector('english', coalesce(array_to_string(NEW.categories, ' '), '')), 'C') ||
                setweight(to_tsvector('english', coalesce(array_to_string(NEW.use_cases, ' '), '')), 'D');
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)
    )
    op.execute(
        sa.text("""
        CREATE TRIGGER apis_fts_trigger
            BEFORE INSERT OR UPDATE ON apis
            FOR EACH ROW EXECUTE FUNCTION apis_fts_update();
        """)
    )

    op.create_table(
        "api_endpoints",
        sa.Column("id", sa.Uuid(as_uuid=False), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("api_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("tags", sa.ARRAY(sa.Text), server_default=sa.text("'{}'")),
        sa.Column("parameters", sa.dialects.postgresql.JSONB),
        sa.Column("request_body", sa.dialects.postgresql.JSONB),
        sa.Column("responses", sa.dialects.postgresql.JSONB),
        sa.Column("auth_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("example_request", sa.dialects.postgresql.JSONB),
        sa.Column("example_response", sa.dialects.postgresql.JSONB),
        sa.Column("deprecated", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
    )

    op.create_index("idx_endpoints_api_id", "api_endpoints", ["api_id"])
    op.create_index("idx_endpoints_method", "api_endpoints", ["method"])
    op.create_index(
        "idx_endpoints_deprecated",
        "api_endpoints",
        ["deprecated"],
        postgresql_where=sa.text("deprecated = false"),
    )
    op.create_index("idx_endpoints_unique", "api_endpoints", ["api_id", "method", "path"], unique=True)

    op.create_table(
        "api_health_log",
        sa.Column("id", sa.Uuid(as_uuid=False), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("api_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("http_status", sa.Integer),
        sa.Column("response_time_ms", sa.Integer),
        sa.Column("dns_resolves", sa.Boolean),
        sa.Column("ssl_valid", sa.Boolean),
        sa.Column("auth_type_detected", sa.Text),
        sa.Column("rate_limit_detected", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("checker_version", sa.Text),
        sa.ForeignKeyConstraint(["api_id"], ["apis.id"], ondelete="CASCADE"),
        postgresql_partition_by="RANGE (checked_at)",
    )

    op.execute(
        sa.text("""
        CREATE TABLE api_health_log_2026_q1
            PARTITION OF api_health_log
            FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
        """)
    )
    op.execute(
        sa.text("""
        CREATE TABLE api_health_log_2026_q2
            PARTITION OF api_health_log
            FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
        """)
    )
    op.execute(
        sa.text("""
        CREATE TABLE api_health_log_2026_q3
            PARTITION OF api_health_log
            FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');
        """)
    )
    op.execute(
        sa.text("""
        CREATE TABLE api_health_log_2026_q4
            PARTITION OF api_health_log
            FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');
        """)
    )

    op.create_index(
        "idx_health_log_api_id", "api_health_log", ["api_id", "checked_at"], postgresql_ops={"checked_at": "DESC"}
    )
    op.create_index("idx_health_log_checked", "api_health_log", ["checked_at"], postgresql_ops={"checked_at": "DESC"})
    op.create_index(
        "idx_health_log_status",
        "api_health_log",
        ["status", "checked_at"],
        postgresql_ops={"checked_at": "DESC"},
    )

    op.create_table(
        "raw_candidates",
        sa.Column("id", sa.Uuid(as_uuid=False), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("source_name", sa.Text, nullable=False),
        sa.Column("source_url", sa.Text),
        sa.Column("raw_name", sa.Text),
        sa.Column("raw_description", sa.Text),
        sa.Column("raw_base_url", sa.Text),
        sa.Column("raw_docs_url", sa.Text),
        sa.Column("raw_auth_type", sa.Text),
        sa.Column("raw_json", sa.dialects.postgresql.JSONB),
        sa.Column("status", sa.Text, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("apis_id", sa.Uuid(as_uuid=False)),
    )

    op.create_index("idx_raw_candidates_status", "raw_candidates", ["status"])
    op.create_index("idx_raw_candidates_source", "raw_candidates", ["source_name"])
    op.create_index("idx_raw_candidates_discovered", "raw_candidates", ["discovered_at"])
    op.create_index(
        "idx_raw_candidates_url",
        "raw_candidates",
        ["raw_base_url"],
        postgresql_where=sa.text("raw_base_url IS NOT NULL"),
    )

    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Uuid(as_uuid=False), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("scraper_name", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text, server_default=sa.text("'running'"), nullable=False),
        sa.Column("candidates_found", sa.Integer, server_default=sa.text("0")),
        sa.Column("candidates_new", sa.Integer, server_default=sa.text("0")),
        sa.Column("candidates_updated", sa.Integer, server_default=sa.text("0")),
        sa.Column("error", sa.Text),
        sa.Column("config_snapshot", sa.dialects.postgresql.JSONB),
    )

    op.create_index("idx_scraper_runs_name", "scraper_runs", ["scraper_name"])
    op.create_index("idx_scraper_runs_started", "scraper_runs", ["started_at"], postgresql_ops={"started_at": "DESC"})
    op.create_index("idx_scraper_runs_status", "scraper_runs", ["status"])

    op.execute(
        sa.text("""
        CREATE OR REPLACE VIEW v_apis_live AS
        SELECT
            id, slug, name, description_llm, base_url, docs_url, spec_url,
            auth_type, auth_notes, signup_required,
            free_tier, rate_limit,
            categories, tags, use_cases, formats, data_formats,
            country, language, company,
            health_score, last_checked, http_status, response_time_ms,
            discovered_at
        FROM apis
        WHERE status = 'active'
          AND health_score >= 50
          AND dns_resolves = true;
        """)
    )
    op.execute(sa.text("COMMENT ON VIEW v_apis_live IS 'Active, healthy APIs suitable for display in search results'"))

    op.execute(
        sa.text("""
        CREATE MATERIALIZED VIEW mv_category_counts AS
        SELECT
            unnest(categories) AS category,
            count(*) AS api_count,
            count(*) FILTER (WHERE auth_type = 'none') AS no_auth_count,
            count(*) FILTER (WHERE status = 'active') AS active_count
        FROM apis
        WHERE status = 'active'
        GROUP BY 1
        ORDER BY 2 DESC;
        """)
    )
    op.create_index("ix_mv_category_counts_category", "mv_category_counts", ["category"], unique=True)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_category_counts")
    op.execute("DROP VIEW IF EXISTS v_apis_live")

    op.drop_index("idx_scraper_runs_status", table_name="scraper_runs")
    op.drop_index("idx_scraper_runs_started", table_name="scraper_runs")
    op.drop_index("idx_scraper_runs_name", table_name="scraper_runs")
    op.drop_table("scraper_runs")

    op.drop_index("idx_raw_candidates_url", table_name="raw_candidates")
    op.drop_index("idx_raw_candidates_discovered", table_name="raw_candidates")
    op.drop_index("idx_raw_candidates_source", table_name="raw_candidates")
    op.drop_index("idx_raw_candidates_status", table_name="raw_candidates")
    op.drop_table("raw_candidates")

    op.drop_index("idx_health_log_status", table_name="api_health_log")
    op.drop_index("idx_health_log_checked", table_name="api_health_log")
    op.drop_index("idx_health_log_api_id", table_name="api_health_log")
    op.drop_table("api_health_log")

    op.drop_index("idx_endpoints_unique", table_name="api_endpoints")
    op.drop_index("idx_endpoints_deprecated", table_name="api_endpoints")
    op.drop_index("idx_endpoints_method", table_name="api_endpoints")
    op.drop_index("idx_endpoints_api_id", table_name="api_endpoints")
    op.drop_table("api_endpoints")

    op.execute("DROP TRIGGER IF EXISTS apis_fts_trigger ON apis")
    op.execute("DROP FUNCTION IF EXISTS apis_fts_update()")

    op.drop_index("idx_apis_pending_enrichment", table_name="apis")
    op.drop_index("idx_apis_pending_validation", table_name="apis")
    op.drop_index("idx_apis_status_score", table_name="apis")
    op.drop_index("idx_apis_status_auth", table_name="apis")
    op.drop_index("idx_apis_fts", table_name="apis")
    op.drop_index("idx_apis_source_names", table_name="apis")
    op.drop_index("idx_apis_formats", table_name="apis")
    op.drop_index("idx_apis_tags", table_name="apis")
    op.drop_index("idx_apis_categories", table_name="apis")
    op.drop_index("idx_apis_country", table_name="apis")
    op.drop_index("idx_apis_last_checked", table_name="apis")
    op.drop_index("idx_apis_health_score", table_name="apis")
    op.drop_index("idx_apis_auth_type", table_name="apis")
    op.drop_index("idx_apis_status", table_name="apis")
    op.drop_index("idx_apis_base_url", table_name="apis")
    op.drop_index("idx_apis_slug", table_name="apis")
    op.drop_table("apis")
