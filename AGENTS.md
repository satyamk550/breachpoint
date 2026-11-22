# AGENTS.md — Team CTF Platform Master Context

## Project Overview

You are a senior full-stack engineer helping build a **self-hosted Team CTF (Capture The Flag) platform**, inspired by [CTFd](https://github.com/CTFd/CTFd.git).

| Property | Value |
|---|---|
| Event size | 25 teams, up to 4 members per team (~100 players) |
| Backend | FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL + Redis |
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Deploy | Docker Compose + Caddy |
| Tests | pytest (backend) + Playwright (frontend/e2e) |

---

## Rules (apply in every task)

1. **Phase discipline** — Work only on the phase given; do not build later phases.
2. **Modular monolith layout**
   - Backend: `backend/app/{core,models,schemas,api,services,workers}`
   - Frontend: `frontend/src/{pages,components,api,hooks}`
3. **Every endpoint** must have Pydantic validation, auth checks, and at least one pytest test.
4. **Never store secrets in code** — use environment variables and a `.env.example` file.
5. **Never log or return** flags, password hashes, or tokens.
6. **Password security** — Hash with argon2 or bcrypt; use HTTP-only secure cookies or short-lived JWT with refresh tokens; add CSRF protection when using cookies.
7. **Race safety** — Use DB transactions and unique constraints for anything race-sensitive: team capacity (max 4 members), one solve per team per challenge, hint unlocks.
8. **After finishing each phase**:
   - Run all tests and fix any failures.
   - Update `docs/PROGRESS.md` with: what was done, how to run it, and what is next.
9. **Event lifecycle** — Read event state only through the lifecycle service (built in Phase 2.5); never compare dates inline in feature code.
10. **Scoring** — Team score is always computed live from solves, hint unlocks, and awards; never stored as a stale total.
11. **Ambiguity** — If something is ambiguous, state your assumption briefly and continue rather than asking many questions.

---

## Folder Structure (target)

```
team-battle/
├── AGENTS.md                  # ← this file
├── docs/
│   └── PROGRESS.md
├── .env.example
├── docker-compose.yml
├── Caddyfile
├── backend/
│   ├── app/
│   │   ├── core/              # config, db, security, lifecycle
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── api/               # FastAPI routers (v1/)
│   │   ├── services/          # business logic
│   │   └── workers/           # background tasks (ARQ)
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/
    │   ├── components/
    │   ├── api/               # typed fetch/axios wrappers
    │   └── hooks/
    ├── index.html
    ├── vite.config.ts
    └── package.json
```

---

## Phase Reference (high-level roadmap)

| Phase | Scope |
|---|---|
| 1 | Scaffold, Docker Compose, Caddy with real client IP, DB, Redis, health check |
| 2 | Auth, roles, rate limiting |
| 2.5 | Lifecycle service: draft/upcoming, live, paused, ended; capabilities; freeze as separate flag |
| 3 | Teams: roster, capacity guard, lock on live, admin swap |
| 4a | Challenges, categories, flags, visibility, prerequisites (404 when hidden) |
| 4b | Hints (idempotent), files (secure download), docs/SCORING.md, admin health check |
| 5 | Submissions, scoring, ScoreEvent log, hint costs, first blood, awards |
| 6 | Scoreboard, SSE realtime, freeze, projector page, stats |
| 7 | Admin panel, audit log, export/import, reset event |
| 8 | Announcements, custom pages, archive mode |
| 9 | Per-team Docker instances (optional) |
| 10 | Security hardening, per-team dynamic flags, anti-cheat |
| 11 | Seed script, E2E tests, load test at 100 and 200 users |
| 12 | Production deploy, backups, runbook |
| 14 | Optional: Attack-Defense |

---

## Key Constraints Summary

- A team has at most **4 members**, enforced inside a transaction with a row lock (`SELECT FOR UPDATE`) and covered by a parallel-join test.
- Event state is read only through the **lifecycle service** and its capabilities.
- Team score is computed from solves, hint unlocks, and awards. **No stored totals in the DB.** A short Redis cache of the computed result is allowed.
- Every score change is also written to the append-only **ScoreEvent** table.
- Hidden, draft, and locked challenges return **404** to players.
- The client IP is trusted only from the **Caddy proxy network**.
- Background jobs use **ARQ**.
