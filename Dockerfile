FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 8000

CMD ["uvicorn", "src.apivault.main:app", "--host", "0.0.0.0", "--port", "8000"]
