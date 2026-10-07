# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (keep minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates git \
  && rm -rf /var/lib/apt/lists/*

# Install uv (https://github.com/astral-sh/uv)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# --- deps layer ---
FROM base AS deps

# Copy only dependency metadata first for better build caching
# NOTE: CI builds with apps/microservices/mission-control as the Docker context,
# so all paths here must be relative to this directory.
COPY pyproject.toml uv.lock ./

# Create venv and sync deps (including runtime)
RUN uv sync --frozen --no-dev

# --- runtime ---
FROM base AS runtime

# Create non-root user before COPY so --chown can reference it.
# Using COPY --chown avoids a slow recursive chown on overlay2 (docker/for-linux#388).
RUN groupadd --system appgroup && useradd --system --gid appgroup --create-home appuser \
  && chown appuser:appgroup /app

# Copy virtual environment from deps stage
COPY --from=deps --chown=appuser:appgroup /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy app source
COPY --chown=appuser:appgroup migrations ./migrations
COPY --chown=appuser:appgroup alembic.ini ./alembic.ini
COPY --chown=appuser:appgroup app ./app

# Copy provisioning templates.
# In-repo these live at `templates/`; runtime path is `/app/templates`.
COPY --chown=appuser:appgroup templates ./templates

# Copy worker scripts.
# In-repo these live at `scripts/`; runtime path is `/app/scripts`.
COPY --chown=appuser:appgroup scripts ./scripts

USER appuser

# Default API port
EXPOSE 8080

# Run the API
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
