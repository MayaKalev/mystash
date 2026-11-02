# MyStash

Paste a link and within seconds see it titled, summarized, categorized and tagged, then browse and filter everything you've saved.

> **Status:** Weeks 1–4 of the MVP are built: a website where you sign up, paste a link and watch it get a title, summary, type and tags, then filter your links, edit tags and delete links. Deployment (Week 5) comes next.

## Run it locally

You need Docker and an [OpenAI API key](https://platform.openai.com/api-keys). Never commit the key.

```bash
export OPENAI_API_KEY=your-key
docker compose up --build
```

- Website: http://localhost:5173
- API: http://localhost:8000 (interactive docs at http://localhost:8000/docs)
- Services: `db` (PostgreSQL 16 + pgvector), `redis`, `api` (FastAPI), `worker` (RQ), `web` (React + Vite).

Changes to files in `web/src/` show up in the browser straight away, without rebuilding.

On a Mac that can't run Docker Desktop (such as macOS 13), [Colima](https://colima.run) works instead: run `colima start --cpu 2 --memory 3` first, then use `docker compose` as normal.

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

The tests use a real PostgreSQL database. By default they connect to `postgresql+psycopg://mystash:mystash@localhost:5432/mystash_test` (create that database first), and you can override that with `TEST_DATABASE_URL`. **The test database is wiped on every run.** They don't need an OpenAI key, because the AI is mocked.

To score the AI against links you tagged by hand, add them to `api/eval/links.csv` and run this from `api/` (it calls the real API, so it costs a little):

```bash
python -m eval.run_eval
```

## Develop the website without Docker

With the API running, from `web/` (needs Node.js 24):

```bash
npm install
npm run dev
```

Checks (the same ones CI runs): `npm run lint` and `npm run build`. The website calls the API at `http://localhost:8000` unless `VITE_API_URL` says otherwise, and the API only accepts calls from the addresses in `CORS_ORIGINS` (default `http://localhost:5173`).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /auth/register | Create an account |
| POST | /auth/login | Log in, returns a JWT |
| GET | /auth/me | Current user (send `Authorization: Bearer <token>`) |
| POST | /items | Save a link: `{"url": "https://..."}`. Returns the item with status `pending` |
| GET | /items | Your saved links, newest first. Optional filters: `?status=`, `?content_type=`, `?tag=` |
| GET | /items/{id} | One saved link, with its summary, type and tags |
| PUT | /items/{id}/tags | Replace the link's tags: `{"tags": ["python", "to read"]}`. Not allowed while it's being processed |
| DELETE | /items/{id} | Delete a saved link |
| GET | /tags | Your tags that are on at least one link, A to Z |
| GET | /health | Health check |

## How saving a link works

1. `POST /items` saves the link with status `pending` and puts a job on the Redis queue.
2. The worker (`app/tasks.py`) picks up the job and sets the status to `processing`.
3. It downloads the page: 10-second timeout, redirects followed, 5 MB limit, web pages only. If the download fails, it tries again, up to 3 times in total, unless retrying can't help (such as a 404).
4. It pulls out the main text with [trafilatura](https://trafilatura.readthedocs.io/), leaving out menus and footers. If there's no main text, it uses the page's description meta tag instead.
5. It sends the text to OpenAI (`app/ai.py`), which returns a title, summary, content type and tags. Tags are made lowercase, and the user's existing tags are reused.
6. The status becomes `done`, or `failed` with a readable `error_message`. If only the AI step fails, the extracted text is kept.

If a site blocks us (401 or 403), or a page has almost no text, the AI works from what little it has, and the summary starts with "Based only on the link:". A dead link such as a 404 still fails.

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
    ai.py           asks OpenAI for the title, summary, type and tags
  alembic/versions/ database migrations
  eval/             scores the AI against hand-tagged links
web/                React website
  src/
    main.jsx        starts React and the router
    App.jsx         the header and the list of pages
    api.js          every call to the API, and the saved login token
    pages/          login and sign-up, the list of links, one link's details
    components/     small pieces used on more than one page
docker-compose.yml  local stack
.github/workflows/  CI: Ruff, mypy and pytest for the API; ESLint and a build for the website
```

## Technical decisions

The code is kept deliberately simple: plain functions, no async code and no clever abstractions.

- **Ordinary (synchronous) FastAPI and SQLAlchemy.** Easier to read and debug than async code, and fast enough for this app.
- **RQ for background jobs.** The simplest Redis job queue for Python: a job is just a normal function.
- **Retries are a plain loop in the job** rather than queue settings, so the whole flow is easy to follow in one file.
- **Tests never use the internet.** Extraction is tested on saved HTML pages in `tests/pages/`, and downloads use httpx's fake network (`MockTransport`).
- **OpenAI with structured output.** `gpt-6-luna` is the default because it's the cheapest current model that isn't scheduled for shutdown. Change it with `OPENAI_MODEL`. The answer is checked against a schema, so the code never has to parse free text.
- **Alembic for migrations**, so the database schema is versioned along with the code.
- **Status and content type are plain text columns**, with the allowed values listed in `models.py`.
- **Tag names are stored lowercase and are unique per user**; the database rejects duplicates.
- **Passwords are hashed with Argon2** (pwdlib), and login returns a JWT that's valid for 7 days.
- **React + Vite in plain JavaScript** for the website, with React Router for the pages and plain CSS. No TypeScript or UI library, so there's less to learn at once.
- **Live status by asking again.** While any link is still `pending` or `processing`, the page asks the API every 2 seconds. Simpler than WebSockets, and it stops once everything is finished.
- **The login token is kept in the browser's `localStorage`**, so you stay logged in. If the API says the token is no longer valid, the website forgets it and goes back to the login page.
- **Tag edits keep where a tag came from:** an AI tag you keep stays `ai`, and tags you add are saved as `user`.
- **pgvector is enabled now** so the v2 semantic search needs no database changes.
