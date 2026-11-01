# MyStash

Paste a link and within seconds see it titled, summarized, categorized and tagged, then browse and filter everything you've saved.

> **Status:** Week 1 of the MVP (foundations) is done: Docker setup, FastAPI, database schema and migrations, and sign-up and login. Saving links, the AI step and the frontend come next.

## Run it locally

You need Docker.

```bash
docker compose up --build
```

- API: http://localhost:8000 (interactive docs at http://localhost:8000/docs)
- Services: `db` (PostgreSQL 16 + pgvector), `redis`, `api` (FastAPI), `worker` (arq). The `web` frontend is added in Week 4.

Migrations run automatically when the API container starts.

## Develop the API without Docker

```bash
cd api
uv sync
cp .env.example .env   # then set JWT_SECRET
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Checks (the same ones CI runs):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run pytest
```

The tests use a real PostgreSQL database with pgvector installed. By default they connect to `postgresql+asyncpg://mystash:mystash@localhost:5432/mystash_test`, and you can override that with `TEST_DATABASE_URL`. **The test database is wiped on every run.**

## API so far

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /auth/register | Create an account |
| POST | /auth/login | Log in, returns a JWT |
| GET | /auth/me | Current user (send `Authorization: Bearer <token>`) |
| GET | /health | Health check |

## Layout

```
api/                FastAPI app, worker, Alembic migrations, tests
  app/              models, routers, auth, settings, worker
  alembic/versions/ database migrations
web/                frontend (Week 4)
docker-compose.yml  local stack
.github/workflows/  CI: Ruff, mypy, pytest on every push
```

## Technical decisions

- **arq** for the job queue: small, async-native and backed by Redis, which fits a FastAPI codebase better than Celery.
- **Async SQLAlchemy 2 + asyncpg**, with **Alembic** for migrations.
- **Enums are stored as text with CHECK constraints** instead of native PostgreSQL enums, so adding a value later is a simple migration.
- **Tag names are lowercase and unique per user**, enforced by the database as well as in code.
- **Passwords are hashed with Argon2** (pwdlib). Login returns the same error for an unknown email and a wrong password, and takes the same time either way.
- **pgvector is enabled now** so the v2 semantic search needs no infrastructure change.
