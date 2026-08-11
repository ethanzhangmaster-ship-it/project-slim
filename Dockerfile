FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY README.md .
COPY src/ src/

RUN pip install --no-cache-dir . --no-build-isolation

FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["python", "-m", "market_ops.product.server", "--host", "0.0.0.0", "--port", "8000", "--root", "/app"]

FROM base AS worker
CMD ["python", "-m", "market_ops.product.doctor", "--root", "/app", "--write"]

FROM base AS scheduler
ENV SCHEDULER_INTERVAL_MINUTES=60
CMD ["python", "-m", "market_ops.cli", "daily-sync"]
