# CLAUDE.md

Guidance for Claude when working on MyStash.

## The project

MyStash: a user signs in, pastes a link, and within seconds sees it titled, summarized,
categorized and tagged, then browses and filters everything they saved. It's a portfolio
project built from a 5-week MVP plan. The goal is a small product that is deployed and works
end to end, not a big unfinished one.

## How to work with Maya

- **Ask before doing anything.** Explain the next step and wait for a yes before writing code,
  committing, pushing or opening a pull request.
- **Keep the code simple.** This is a junior-level project. Prefer plain, readable code over clever
  code: ordinary (non-async) functions, no extra abstractions, short comments that explain *why*.
  If something can be done with fewer moving parts, do that.
- **One branch and one pull request per week of the plan.** Branches are named `mystash-v1`,
  `mystash-v1-2`, `mystash-v1-3`, and so on. Wait until Maya has merged one week before starting the
  next, and start the next branch from the updated `main`.


## Plan and status

| Week | What | Status |
| --- | --- | --- |
| 1 | Foundations: repo layout, Docker, FastAPI, models, Alembic, auth (JWT), CI | Merged (MayaKalev/mystash#1) |
| 2 | Ingestion: `POST /items`, queue + worker, fetching, text extraction, retries | Merged (MayaKalev/mystash#2) |
| 3 | AI tagging: LLM with structured output, tag normalization and reuse, mocked in tests, eval set of 30–50 hand-tagged URLs | Not started |
| 4 | Frontend (`/web`): login and signup, save a link, item list with live status and filters, item detail with tag editing, delete | Not started |
| 5 | Deploy (API, worker, managed Postgres and Redis, frontend), Sentry, rate limiting, README polish | Not started |

Out of scope for the MVP: screenshots/OCR, semantic search, browser extension, collections,
integrations, mobile. pgvector is installed now only so v2 semantic search needs no database change.

Known follow-ups from Week 2:
- Permanent errors (such as 404) are retried 3 times; they shouldn't be.
- `GET /items` and `GET /items/{id}` don't exist yet (they're in the plan's API list).
- Before deploying: block URLs that point to the server's own network.
- Extraction hasn't been checked against real websites yet.

## Stack and layout

FastAPI + SQLAlchemy 2 (sync, psycopg) + Alembic, PostgreSQL 16 with pgvector, Redis + RQ for
background jobs, pip with pinned `requirements.txt`. Python 3.12 in Docker.

```
api/
  app/
    main.py         creates the FastAPI app
    config.py       settings from environment variables (JWT_SECRET is required)
    database.py     engine, SessionLocal, get_db
    models.py       tables: users, items, tags, item_tags
    schemas.py      request and response models
    auth.py         password hashing, JWT, get_current_user
    queue.py        the RQ queue
    tasks.py        worker jobs (process_item: fetch, extract, save)
    routers/        endpoints (auth.py, items.py)
  alembic/versions/ migrations; add a new one for every schema change
  tests/            pytest; tests/pages/ holds saved HTML pages
web/                frontend (Week 4)
docker-compose.yml  db, redis, api, worker
```

Data rules: item `status` is `pending`, `processing`, `done` or `failed`. `content_type` is
`article`, `video`, `repo`, `tool` or `other`. Tag names are lowercase and unique per user.
`item_tags.source` is `ai` or `user`.

## Commands

Run the whole stack:

```bash
docker compose up --build
```

API checks, from `api/` with the virtual environment active (the same checks CI runs):

```bash
ruff check . && ruff format --check .
```
```bash
mypy app --ignore-missing-imports
```
```bash
pytest
```

Tests need a PostgreSQL database at
`postgresql+psycopg://mystash:mystash@localhost:5432/mystash_test` (override with
`TEST_DATABASE_URL`). The tables are dropped and recreated for every test.

## Testing rules

- Tests never use the internet. Use saved HTML in `tests/pages/` and `httpx.MockTransport`
  (`fetch_html` takes a `transport` argument for this). Mock the LLM in Week 3.
- Use a real PostgreSQL database, not SQLite.
- Run the checks above before every commit.

## Cloud sandbox notes

When working from a Claude cloud session:
- Most websites are blocked, so real-site checks have to happen on Maya's Mac.
- Docker builds there need the sandbox's proxy certificate. Add it only through temporary files
  and never commit it.
- Docker Hub can rate-limit image pulls; wait and retry.
