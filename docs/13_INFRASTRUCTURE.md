# Infrastructure & Deployment
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Deployment Options

### Option A: Single-Host Docker Compose (Recommended)
Self-hosted on one machine. Simplest, lowest cost, all features available.

### Option B: Managed Database + App Server
PostgreSQL on Supabase/Neon (free tier), app on Fly.io or Railway.

### Option C: Cloud VM
Single VM on any cloud (Hetzner, DigitalOcean, AWS EC2). Docker Compose still used.

---

## 2. Minimum Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 2 cores | 4 cores |
| RAM | 8 GB | 16 GB |
| Disk | 50 GB SSD | 200 GB SSD |
| Network | 100 Mbps | 1 Gbps |

RAM breakdown (recommended):
- PostgreSQL: 4 GB (`shared_buffers=1GB`, `work_mem=256MB`)
- API server: 512 MB
- Workers (normalizer + validator + enrichment): 2 GB total
- Ollama (local LLM): 4 GB (for nomic-embed-text model)
- OS + overhead: 2 GB

Disk breakdown (90k APIs at full scale):
- PostgreSQL data: ~10 GB (apis table + indexes + health_log)
- Raw candidates archive: ~5 GB
- pgvector index: ~2 GB (1536-dim vectors × 90k records)
- Ollama models: ~1 GB (nomic-embed-text)
- Logs: ~5 GB (30-day rolling)
- Playwright browsers: ~500 MB

---

## 3. Docker Compose Configuration

```yaml
# docker-compose.yml
version: "3.9"

services:

  db:
    image: pgvector/pgvector:pg16
    restart: always
    environment:
      POSTGRES_DB: apivault
      POSTGRES_USER: apivault
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    ports:
      - "127.0.0.1:5432:5432"  # Only expose locally
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U apivault"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: docker/api/Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql://apivault:${POSTGRES_PASSWORD}@db:5432/apivault
      ADMIN_KEY: ${ADMIN_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS:-*}
    ports:
      - "0.0.0.0:8000:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql://apivault:${POSTGRES_PASSWORD}@db:5432/apivault
      OLLAMA_URL: http://ollama:11434
      LLM_BACKEND: ${LLM_BACKEND:-ollama}
      CLAUDE_API_KEY: ${CLAUDE_API_KEY:-}
    depends_on:
      db:
        condition: service_healthy

  scheduler:
    build:
      context: .
      dockerfile: docker/scheduler/Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql://apivault:${POSTGRES_PASSWORD}@db:5432/apivault
      GITHUB_TOKEN: ${GITHUB_TOKEN:-}
    depends_on:
      db:
        condition: service_healthy

  ollama:
    image: ollama/ollama:latest
    restart: always
    volumes:
      - ollamadata:/root/.ollama
    ports:
      - "127.0.0.1:11434:11434"
    # GPU support (uncomment if available):
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]
    profiles:
      - local-llm  # Only start with: docker compose --profile local-llm up

  prometheus:
    image: prom/prometheus:latest
    restart: always
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheusdata:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    profiles:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    restart: always
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafanadata:/var/lib/grafana
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - prometheus
    profiles:
      - monitoring

volumes:
  pgdata:
  ollamadata:
  prometheusdata:
  grafanadata:
```

---

## 4. PostgreSQL Tuning

```ini
# docker/postgres/postgresql.conf

# Memory
shared_buffers = 2GB           # 25% of RAM
effective_cache_size = 6GB     # 75% of RAM
work_mem = 256MB               # Per sort/hash operation
maintenance_work_mem = 512MB   # For VACUUM, CREATE INDEX

# Parallelism
max_parallel_workers_per_gather = 2
max_worker_processes = 8
max_parallel_workers = 4

# WAL
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 2GB

# Planner
random_page_cost = 1.1         # SSD (lower than default 4.0)
effective_io_concurrency = 200 # SSD

# Connections
max_connections = 100
```

---

## 5. Dockerfile (API)

```dockerfile
# docker/api/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev

# Copy application
COPY src/ ./src/

ENV PYTHONPATH=/app
CMD ["uv", "run", "uvicorn", "src.api.main:app",
     "--host", "0.0.0.0", "--port", "8000",
     "--workers", "2",
     "--loop", "uvloop",
     "--http", "httptools"]
```

---

## 6. Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/diesesschnitzel/dummy apivault
cd apivault

# 2. Create environment file
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD at minimum

# 3. Pull images and build
docker compose build
docker compose pull

# 4. Start database
docker compose up -d db

# 5. Run migrations
docker compose run --rm worker python -m src.db.migrate

# 6. Pull Ollama model (if using local LLM)
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull nomic-embed-text

# 7. Start all services
docker compose up -d
# or with local LLM:
docker compose --profile local-llm up -d

# 8. Bootstrap first ingest (runs highest-yield scrapers once)
docker compose exec scheduler python -m src.scheduler.bootstrap

# 9. Verify
curl http://localhost:8000/health
curl http://localhost:8000/stats
```

---

## 7. Data Backup

```bash
# Makefile target: make backup
pg_dump -h localhost -U apivault -Fc apivault > backup_$(date +%Y%m%d).dump

# Restore
pg_restore -h localhost -U apivault -d apivault backup_20260415.dump

# Automated: daily backup via cron (add to crontab)
0 2 * * * docker compose exec db pg_dump -U apivault -Fc apivault > /backups/apivault_$(date +%Y%m%d).dump
```

---

## 8. Updating

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker compose build

# Run any new migrations
docker compose run --rm worker python -m src.db.migrate

# Rolling restart (API stays up during worker restarts)
docker compose up -d --no-deps api
docker compose up -d --no-deps worker scheduler
```

---

## 9. Scaling (If Needed)

For larger deployments (>500k APIs, high query traffic):

**Horizontal read scaling:**
```yaml
# docker-compose.scale.yml
services:
  api:
    deploy:
      replicas: 4
  # Add nginx load balancer in front
```

**Separate worker hosts:**
- Move `worker` and `scheduler` to a separate machine
- Both connect to same PostgreSQL over network

**Read replica for queries:**
```
Primary PostgreSQL → Streaming replication → Read replica
API server reads from replica
Writes (validation, enrichment) go to primary
```

**At 1M+ APIs:** Migrate to pgvector with HNSW index (more accurate ANN search):
```sql
-- Replace IVFFlat with HNSW for higher recall
DROP INDEX idx_apis_embedding;
CREATE INDEX idx_apis_embedding_hnsw ON apis
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```
