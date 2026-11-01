# MyStash

Paste a link and within seconds see it titled, summarized, categorized and tagged, then browse and filter everything you've saved.

> **Status:** Week 1 of the MVP (foundations) is done: Docker setup, FastAPI, database schema and migrations, and sign-up and login. Saving links, the AI step and the frontend come next.

## Run it locally

You need Docker.

```bash
docker compose up --build
```

- API: http://localhost:8000 (interactive docs at http://localhost:8000/docs)
- Services: `db` (PostgreSQL 16 + pgvector), `redis`, `api` (FastAPI), `worker` (RQ). The `web` frontend is added in Week 4.

Migrations run automatically when the API container starts.

## Develop the API without Docker

Start just the database and Redis with Docker, then run the API on your machine:

```bash
docker compose up -d db redis
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export JWT_SECRET=any-long-random-string-for-local-dev
alembic upgrade head
uvicorn app.main:app --reload
```

Checks (the same ones CI runs):

```bash
ruff check . && ruff format --check .
mypy app --ignore-missing-imports
pytest
```

The tests use a real PostgreSQL database. By default they connect to `postgresql+psycopg://mystash:mystash@localhost:5432/mystash_test` (create that database first), and you can override that with `TEST_DATABASE_URL`. **The test database is wiped on every run.**

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
  app/
    main.py         creates the FastAPI app
    config.py       settings, read from environment variables
    database.py     database connection
    models.py       database tables
    schemas.py      request and response shapes
    auth.py         password hashing and login tokens
    routers/        the API endpoints
    tasks.py        background jobs for the worker
  alembic/versions/ database migrations
web/                frontend (Week 4)
docker-compose.yml  local stack
.github/workflows/  CI: Ruff, mypy, pytest on every push
```

## Technical decisions

The code is kept deliberately simple: plain functions, no async code and no clever abstractions.

- **Ordinary (synchronous) FastAPI and SQLAlchemy.** Easier to read and debug than async code, and fast enough for this app.
- **RQ for background jobs.** The simplest Redis job queue for Python: a job is just a normal function.
- **Alembic for migrations**, so the database schema is versioned along with the code.
- **Status and content type are plain text columns**, with the allowed values listed in `models.py`.
- **Tag names are stored lowercase and are unique per user**; the database rejects duplicates.
- **Passwords are hashed with Argon2** (pwdlib), and login returns a JWT that's valid for 7 days.
- **pgvector is enabled now** so the v2 semantic search needs no database changes.
