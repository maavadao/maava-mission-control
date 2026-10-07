# Mission Control Backend (FastAPI)

This directory contains the **Mission Control backend API** (FastAPI + SQLModel) and its database migrations (Alembic).

- Default API base URL: `http://localhost:8000`
- Health endpoints: `/healthz`, `/readyz`
- API routes: `/api/v1/*`

## Requirements

- Python **3.12+**
- [`uv`](https://github.com/astral-sh/uv) (recommended; used by this repo)
- Postgres (local or Docker)

## Quick start (local backend + Docker Postgres)

From this directory:

```bash
# start dependencies
cp .env.example .env
uv sync --extra dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl -f http://localhost:8000/healthz
```

## Cloud Run deployment requirements

Cloud Run must provide these runtime settings for this service:

- `DATABASE_URL`
- `DATABASE_SCHEMA=mission_control` (or another dedicated schema name)
- `AUTH_MODE=local` or a complete Clerk configuration
- `LOCAL_AUTH_TOKEN` when `AUTH_MODE=local`
- Optional `BASE_URL` as the public Mission Control URL for gateway/provisioning flows

If you store values in GCP Secret Manager, expose them to Cloud Run as environment variables with these same names so the app can read them directly at startup.

## Configuration / environment variables

Backend settings are defined in `app/core/config.py` via `pydantic-settings`.

The backend loads env files in this order:

1. `.env` in this directory (preferred)
2. `.env` (current working directory)

A starter file exists at `.env.example`.

### Core

- `ENVIRONMENT` (default: `dev`)
  - In `dev`, if you **don’t** explicitly set `DB_AUTO_MIGRATE`, the backend defaults it to `true`.
- `LOG_LEVEL` (default: `INFO`)
- `DATABASE_URL`
  - Point this at the existing Barrsa Postgres database when running Mission Control alongside the main app.
- `DATABASE_SCHEMA`
  - Default: `mission_control`
  - Mission Control creates and uses this schema inside the shared database so its tables do not collide with Barrsa tables like `users` and `agents`.
- `CORS_ORIGINS` (comma-separated)
  - Example: `http://localhost:3000`
- `BASE_URL` (optional; required only for gateway provisioning/agent heartbeat templates)

### Database lifecycle

- `DB_AUTO_MIGRATE`
  - If `true`: on startup, the backend attempts to run Alembic migrations (`alembic upgrade head`).
  - If there are **no** Alembic revision files yet, it falls back to `SQLModel.metadata.create_all`.

### Security headers

Security response headers added to every API response. Set any variable to blank to disable the corresponding header.

- `SECURITY_HEADER_X_CONTENT_TYPE_OPTIONS` (default: `nosniff`)
- `SECURITY_HEADER_X_FRAME_OPTIONS` (default: `DENY`)
- `SECURITY_HEADER_REFERRER_POLICY` (default: `strict-origin-when-cross-origin`)
- `SECURITY_HEADER_PERMISSIONS_POLICY` (default: blank — disabled)

### Auth (Clerk)

Clerk is used for user authentication (optional for local/self-host in many setups).

- `CLERK_SECRET_KEY` (required)
  - Used to fetch user profile fields (email/name) from Clerk when JWT claims are minimal.
- `CLERK_API_URL` (default: `https://api.clerk.com`)
- `CLERK_VERIFY_IAT` (default: `true`)
- `CLERK_LEEWAY` (default: `10.0`)

## Database migrations (Alembic)

Migrations live in `backend/migrations/versions/*`.

Common commands:

```bash
cd backend

# apply migrations
uv run alembic upgrade head

# create a new migration (example)
uv run alembic revision --autogenerate -m "add foo"
```

Notes:

- The backend can also auto-run migrations on startup when `DB_AUTO_MIGRATE=true`.
- The database URL is normalized so `postgresql://...` becomes `postgresql+psycopg://...`.

## Running tests / lint / typecheck

From repo root (recommended):

```bash
make backend-lint
make backend-test
make backend-coverage
```

`make backend-lint` runs backend format checks (`isort`, `black`), lint (`flake8`), and typecheck (`mypy`) in one command.

Or from `backend/`:

```bash
cd backend
uv run pytest
uv run isort . --check-only --diff
uv run black . --check --diff
uv run flake8 --config .flake8
uv run mypy
```

Formatting:

```bash
make backend-format
make backend-format-check
```

## Scripts

Backend scripts live in `backend/scripts/`:

- `export_openapi.py` – export OpenAPI schema
- `seed_demo.py` – seed demo data (if applicable)
- `sync_gateway_templates.py` – sync repo templates to an existing gateway

Run with:

```bash
cd backend
uv run python scripts/export_openapi.py
```

## Troubleshooting

### Backend can’t connect to Postgres

- If you started Postgres via compose, make sure it is healthy:

  ```bash
  docker compose -f compose.yml --env-file .env ps
  docker compose -f compose.yml --env-file .env logs -f --tail=200 db
  ```

- If backend runs **locally** (not in compose), `DATABASE_URL` should usually point at `localhost`.

### CORS issues from the frontend

- Set `CORS_ORIGINS=http://localhost:3000` (or a comma-separated list) in `backend/.env`.
- Restart the backend after changing env vars.

### Alembic / migrations not applying

- If you want deterministic behavior, run migrations manually:

  ```bash
  cd backend
  uv run alembic upgrade head
  ```

- If `DB_AUTO_MIGRATE=false`, the backend may use `create_all` instead of Alembic.
