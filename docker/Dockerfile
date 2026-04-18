# Jarvis — production container image.
# Build: docker build -f docker/Dockerfile -t jarvis:latest .
# Run:   docker compose -f docker/docker-compose.yml up

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE /app/
COPY jarvis /app/jarvis
COPY web /app/web

RUN pip install --upgrade pip && pip install -e ".[anthropic,openai]"

RUN useradd --system --create-home --shell /usr/sbin/nologin jarvis \
 && mkdir -p /app/var /app/var/workspaces /app/var/logs \
 && chown -R jarvis:jarvis /app

USER jarvis

ENV JARVIS_HOST=0.0.0.0 \
    JARVIS_PORT=8765 \
    JARVIS_DATA_DIR=/app/var

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8765/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["jarvisd"]
