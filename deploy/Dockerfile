# E14.4.1 — Lean Container Runtime for the LaunchForge GameFactory OS
#
# Build context MUST be the repository root (the parent of launchforge/), e.g.
#   docker build -f launchforge/deploy/Dockerfile -t launchforge-worker .
#
# The image is intentionally tiny and backend-free: pure-Python orchestrator,
# JSONL stores on a mounted volume, credentials on a read-only secret volume.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Isolated venv (Lean: only what the worker imports)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY launchforge/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# The launchforge package (monetization + deploy worker)
COPY launchforge /app/launchforge
COPY launchforge/deploy/worker.py /app/deploy/worker.py
RUN chmod +x /app/deploy/worker.py

# Volumes the operator mounts at runtime:
#   /app/data/stores      JSONL DecisionStore (state)   -> named volume
#   /app/data/checkpoints runtime checkpoints            -> named volume
#   /app/credentials      per-game secrets (read-only)   -> secret volume
VOLUME ["/app/data/stores", "/app/data/checkpoints", "/app/credentials"]

ENTRYPOINT ["python", "/app/deploy/worker.py"]
