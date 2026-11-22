# Progress Log

## Phase 1 — Scaffold (complete)

**Date:** 2026-11-22

### What was done

- Created monorepo with `backend/` (FastAPI + Python 3.12) and `frontend/` (Vite + React + TypeScript + Tailwind).
- Configured pydantic-settings and `.env.example`; Postgres credentials and app connection URL are configured from environment variables.
- Set up SQLAlchemy 2 async engine (`asyncpg`) and async-friendly Alembic; initial migration creates only `users`, `teams`, and `configs`.
- Implemented `GET /api/v1/health` to check PostgreSQL (`SELECT 1`) and Redis (`PING`), returning `503` if either is unavailable.
- Added `get_client_ip()` helper that trusts `X-Real-IP` only from the fixed `172.28.0.0/16` internal proxy subnet.
- Configured Caddy to set `X-Real-IP` inside the API reverse-proxy block.
- Docker Compose starts `postgres`, `redis`, `backend`, `frontend`, and `caddy`; dependency healthchecks gate backend startup.
- Added an opt-in `test` Compose profile with disposable PostgreSQL (localhost port 55432) and Redis (localhost port 56379); backend tests use real services, not SQLite.
- Added `ruff` (backend lint/format), ESLint + TypeScript strict (frontend), `.pre-commit-config.yaml`, and the GitHub Actions workflow.
- Added the React 18 + Vite + TypeScript + Tailwind health dashboard, with typed health API calls, live backend/PostgreSQL/Redis indicators, and manual/automatic refresh.
- Added the Vite development Docker target used by Compose and a separate production asset build stage.
- Updated CI to run backend tests against PostgreSQL and Redis service containers, alongside frontend lint and type-check.

### How to run

```bash
# Docker (all services; copy .env.example to .env and replace placeholders)
docker compose up --build -d
docker compose exec backend alembic upgrade head
# → open http://localhost when HTTP_PORT=80; otherwise use http://localhost:<HTTP_PORT>

# Backend tests (real PostgreSQL and Redis; from repository root)
docker compose --profile test up -d postgres-test redis-test
docker compose --profile test run --rm backend-test alembic upgrade head
docker compose --profile test run --rm backend-test
docker compose --profile test rm -sf postgres-test redis-test

# Local frontend checks
cd frontend && npm install
npm run type-check && npm run lint

# CI runs backend pytest against service containers and frontend lint/type-check
```

### Phase 1 verification

- `docker compose up --build -d` built and started the full stack.
- `npm run type-check`, `npm run lint`, and `npm run build` passed in `frontend/`.
- The backend CI test command passed: 4 tests against the test-profile PostgreSQL and Redis containers.
- `docker build --target production-build ...` completed successfully.
- Through Caddy, `/api/v1/health` returned HTTP 200 with database and Redis `ok`.
- The default host port 80 was occupied by another local service during verification; the configured `HTTP_PORT` was used for Team Battle.

### Health endpoint

```
GET http://localhost:<HTTP_PORT>/api/v1/health
```

### What is next

**Phase 2** — Auth: registration, login, JWT + HTTP-only cookie, roles (`admin` / `player`), rate limiting.

## Phase 1.5 — Frontend foundation (complete)

- Added reusable, keyboard-accessible UI primitives, the responsive app shell, semantic design tokens, self-hosted fonts, and status, 404, and error routes. No later-phase product functionality was introduced.
- Centralized the platform name in `frontend/src/config/brand.ts` with a `VITE_APP_NAME` override, and documented the preserved visual system and future-screen rules in `docs/DESIGN.md`.
- Added the typed API client, TanStack Query health polling with hidden-tab pause and failure backoff, and MSW-backed tests for healthy, degraded, unreachable, refresh, error-boundary, and accessibility behavior.
- Updated CI to run frontend type-checking, lint, tests, and production build. Upgraded Vitest to a patched compatible release; `npm audit` reports zero vulnerabilities.
- Removed the 360px root minimum that caused horizontal overflow when the browser scrollbar reduced the content viewport.

### Phase 1.5 verification

- `npm run type-check` — passed.
- `npm run lint` — passed.
- `npm test` — 2 test files and 6 tests passed.
- `npm run build` — passed.
- `npm audit` — 0 vulnerabilities.
- `docker compose up --build -d frontend` — rebuilt and started the frontend service without changing backend code or Compose configuration.
- Through Caddy at `http://localhost:8080`, the page showed `3 / 3 healthy`; `/api/v1/health` returned HTTP 200.
- Browser checks at 360px, 1280px, and 1920px found no horizontal overflow. Keyboard checks verified the skip link and mobile navigation; the 404 and error routes rendered, and the browser console had no errors.

### What is next

**Phase 2** — Auth: registration, login, JWT + HTTP-only cookie, roles (`admin` / `player`), rate limiting.

