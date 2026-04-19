# APIVault Worker Dockerfile
# Handles background jobs: validation, enrichment, pipeline processing

FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
        playwright \
        gconf-service \
        libasound2 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libnspr4 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        xdg-utils \
        fonts-liberation \
        libu2f-udev \
        libvulkan1 && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --shell /bin/bash apivault

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

# Copy application code
COPY src/ ./src/

# Install Playwright browsers
RUN /app/.venv/bin/playwright install --with-deps chromium

# Set environment variables
ENV PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER apivault

CMD ["python", "-m", "src.apivault.worker"]
