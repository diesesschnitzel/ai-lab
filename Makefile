# APIVault Makefile
# Common development and deployment commands

.PHONY: help install lint typecheck test test-cov docker-build docker-up docker-down migrate backup clean

# Default target
help:
	@echo "APIVault - Makefile Targets"
	@echo ""
	@echo "Development:"
	@echo "  install       Install dependencies"
	@echo "  lint          Run Ruff linter"
	@echo "  typecheck     Run mypy type checker"
	@echo "  test          Run pytest"
	@echo "  test-cov      Run pytest with coverage"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build  Build all Docker images"
	@echo "  docker-up     Start all services"
	@echo "  docker-up-llm Start with local LLM"
	@echo "  docker-up-mon Start with monitoring"
	@echo "  docker-down   Stop all services"
	@echo "  docker-logs   Show logs"
	@echo ""
	@echo "Database:"
	@echo "  migrate       Run database migrations"
	@echo "  backup        Create database backup"
	@echo ""
	@echo "Operations:"
	@echo "  serve         Start API server locally"
	@echo "  worker        Start worker locally"
	@echo "  scheduler     Start scheduler locally"
	@echo "  ingest-bootstrap  Run first ingest"
	@echo "  clean         Remove build artifacts"

# Development
install:
	uv sync --all-extras

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# Docker
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-up-llm:
	docker compose --profile local-llm up -d

docker-up-mon:
	docker compose --profile monitoring up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# Database
migrate:
	docker compose run --rm worker python -m src.apivault.db.migrate

backup:
	@mkdir -p backups
	docker compose exec db pg_dump -U apivault -Fc apivault > backups/apivault_$$(date +%Y%m%d_%H%M%S).dump

# Operations
serve:
	uv run uvicorn src.apivault.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run python -m src.apivault.worker

scheduler:
	uv run python -m src.apivault.scheduler

ingest-bootstrap:
	docker compose exec scheduler python -m src.apivault.scheduler.bootstrap

# Cleanup
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
