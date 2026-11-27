# Team Battle CTF

A self-hosted Capture The Flag platform for up to 25 teams and ~100 players.

## Stack

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Backend  | FastAPI · SQLAlchemy 2 · Alembic · Postgres · Redis |
| Frontend | React 18 · Vite · TypeScript · Tailwind CSS |
| Infra    | Docker Compose · Caddy                      |

## Phase status

| Phase | Status |
|---|---|
| 1–3 | Complete |
| 4a | Complete |
| 4b backend | Complete |
| 4b frontend | In progress — player hints/files, admin hint editing, upload, and health route added; file listing/editing awaits a backend read contract |
| 5 | Complete |
| 6+ | Not started |

## Quick Start (Docker)

```bash
# 1. Copy and fill in environment variables
cp .env.example .env
# Edit .env — set SECRET_KEY and replace the database password placeholder.

# 2. Build and start all services
docker compose up --build -d

# 3. Run database migrations
docker compose exec backend alembic upgrade head

# 4. Open in browser (use the configured HTTP_PORT if 80 is occupied)
#    http://localhost
```

## Development (local)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy the example environment and set DATABASE_URL/REDIS_URL for local Postgres + Redis.
cp ../.env.example .env
# DATABASE_URL must use postgresql+asyncpg; configure SECRET_KEY as well.

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Running Tests

```bash
# Backend tests use a real, throwaway PostgreSQL database and Redis.
# Start the test dependencies (test Postgres is bound only to localhost:55432).
docker compose --profile test up -d postgres-test redis-test

# Apply the migration to the test database.
docker compose --profile test run --rm backend-test alembic upgrade head

# Run backend tests inside the test network.
docker compose --profile test run --rm backend-test

# Remove only the test containers; Postgres data is temporary (tmpfs).
docker compose --profile test rm -sf postgres-test redis-test

# Frontend
cd frontend
npm run type-check
npm run lint
```

## Health Check

```
GET http://localhost:<HTTP_PORT>/api/v1/health
```

Returns `200 OK` with database and Redis status when everything is healthy.

## Docs

- [Progress log](docs/PROGRESS.md)
- [Architecture (phase-by-phase)](AGENTS.md)
