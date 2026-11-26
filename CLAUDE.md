# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with code in this repository.

## Project

A self-hosted LLM assistant: one streaming chat endpoint that answers from one markdown knowledge base. Users log in, and tags decide which files each user's answers may come from. There are no projects — the prompt, models and other options are settings. Scope and open questions are in `docs/requirements.md`.

- **Framework:** FastAPI + Uvicorn
- **Schemas:** Pydantic v2
- **Model server:** Ollama, called only through the OpenAI-compatible API (`openai` client), so a hosted API can be swapped in by URL
- **Search index:** Qdrant, one collection (`COLLECTION`)
- **Database:** PostgreSQL via SQLAlchemy 2.0 (classic `Column(...)` style) + Alembic — users, tags, the tags of each file, and conversations with their messages. Queries are built with SQLAlchemy (`select`, `delete`, the ORM), never written as SQL strings (the one exception is `CREATE DATABASE` in `scripts/create_database.py`, which has no builder)
- **No background jobs.**

The API is published on host port **8000**, bound to `127.0.0.1`. Routes are versioned under `/v1`.

## Layout

```
app/
  main.py        App entrypoint: create_app() builds the shared clients, CORS, router registration
  config.py      Settings (from the environment)
  api/           FastAPI routers — thin
  schemas/       Pydantic request/response models (the API contract)
  models/        SQLAlchemy models: User, Tag, File, Conversation, Message and the user_tags / file_tags tables
  services/      Logic — retrieval, prompt building, users, tags, model calls, the search index, the conversation log
  core/          Cross-cutting: FastAPI dependencies, the login and admin checks, database, security
  constants/     Shared prompt rules and limits
tests/           pytest suite (harness in tests/conftest.py)
alembic/         Migrations
scripts/         init.sh (runs before the api starts), create_database (the database in DATABASE_URL, if missing), seed_admin (the admin from ADMIN_EMAIL / ADMIN_PASSWORD), import_files (rows for pages already on disk), reindex (full rebuild)
deploy/          Dockerfile
docs/            requirements.md — purpose, scope, later work, open questions
kb/              Knowledge base pages: uploads or a checkout (not in git)
```

## Commands

There is **no local virtualenv** — run everything in Docker. `docker-compose.yml` is in this repo.

```bash
cp env.example .env                                    # set SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
mkdir -p kb                                            # otherwise Docker creates it as root and the api cannot write
docker compose up -d --build                           # api + ollama + qdrant + postgres
docker compose exec ollama ollama pull gemma3:4b       # DEFAULT_MODEL
docker compose exec ollama ollama pull bge-m3          # EMBEDDING_MODEL
curl -X POST -H "Authorization: Bearer <token>" -F "files=@page.md" -F "tags=<tag id>" http://localhost:8000/v1/files
```

The api container runs `scripts/init.sh` before it starts, which creates the database if the server lacks it (`scripts.create_database`), applies the migrations (`alembic upgrade head`) and seeds the admin (`scripts.seed_admin`: created from `ADMIN_EMAIL` and `ADMIN_PASSWORD` only if no user has that email, never updated afterwards); put any other start-up step there. A command given to `docker compose run` replaces it, so tests and scripts skip it. After changing a model, add a migration: `docker compose run --rm api alembic revision --autogenerate -m "..."` writes it inside the container, so copy it out or write it by hand in `alembic/versions/`.

Uploading or deleting a page indexes just that page. There is no rebuild endpoint: `python -m scripts.reindex` drops the index and embeds every page again, which takes hours for a large knowledge base, and is only for pages edited on disk or a changed `EMBEDDING_MODEL`. To only give pages on disk their database rows and copy tags onto the index, run `python -m scripts.import_files [--tag NAME]`; it embeds nothing.

The code is copied into the image, not mounted: **rebuild after a code change** (`docker compose up -d --build api`). `kb/` is mounted. Settings are read once at startup, so restart the api after editing `.env`.

Swagger at `/docs` (the **Authorize** button takes the token from `POST /v1/auth/login`), health check at `/health`.

## Tests

```bash
docker compose build api && docker compose run --rm --no-deps api pytest
```

`--no-deps` keeps Ollama, Qdrant and Postgres from starting; the tests don't need them. The compose file requires `.env` to exist.

Tests build the app with `create_app(settings, llm, store, sessions)`, passing a `FakeLLM`, a `Store` over `QdrantClient(":memory:")` and a session factory over a SQLite file created from the models (the `env` fixture in `tests/conftest.py`). The fixture's client is logged in as an admin; `as_user(email, *tag_names)` returns the headers of a new user, `reindex()` indexes the pages on disk as the script does, and `{"Authorization": ""}` sends a request with no login. Because tests run on SQLite, models use SQLAlchemy's generic types (`Uuid`, not the Postgres dialect's) and must not rely on database-level cascades. `tests/conftest.py` blocks every socket connection, so a test that reaches a real model server or index fails.

When writing tests:
- Inject fakes through `create_app`; never loosen the network guard to make a test pass.
- Point `Settings` at `tmp_path` for `kb_root`, so nothing touches the real folder.
- For anything tags decide, assert that a restricted section is absent from what the model was given, as `tests/test_access.py` does.
- Assert on what the model was given (`llm.chats`, `llm.embedded`), not only on the reply — the fake always answers the same.
- When you change behaviour, update or add the tests that cover it and run them.

There is **no linter or formatter** configured.

## Core Rules

1. **Keep it simple.** Write the most straightforward solution that works. Prefer fewer lines, fewer abstractions, and existing helpers over new machinery. Don't add layers, config options, or generality the task didn't ask for.

2. **No premature optimization.** Solve the actual problem in front of you. Don't build for hypothetical future requirements — the "Later" list in `docs/requirements.md` is not a to-do list for the current task.

3. **Match existing patterns.** Before writing new code, look at neighbouring files and follow their style, naming, and structure. Reuse what's in `app/core/`, `app/services/` and `app/constants/` instead of duplicating logic.

4. **Minimal footprint.** Change only what the task requires. Don't refactor, rename, or reformat unrelated code.

5. **No unnecessary comments.** Only comment non-obvious logic — a constraint that isn't self-evident, or a decision whose reason would otherwise be lost. Don't narrate what the code already says. Keep docstrings to what a reader needs.

## Architecture

Request flow is a two-layer pattern — keep new code on these seams:

```
app/api/*        Routers — thin. Validate via app/schemas, resolve dependencies, delegate.
app/services/*   Logic. Every model, index, file and database call lives here.
```

**App wiring** (`app/main.py`): `create_app()` is a factory (Uvicorn runs it with `--factory`). It loads settings, builds one `LLM`, one `Store` and one database session factory, and puts all four on `app.state`. Routers register with the `/v1` prefix; the conversations router is built by `create_router(models)`, so the request's `model` field is an enum of the models the settings allow; `/health` is at the root. CORS allows `ALLOWED_ORIGINS`. There is no module-level `app`, `settings` or database engine singleton — that is what lets tests pass in fakes.

**Dependencies** (`app/core/dependencies.py`): routers reach the shared objects only through `get_settings`, `get_llm`, `get_store`, `get_db` (one session per request) and `get_sessions` (the factory, for work that outlives the request). `get_current_user` reads the login token from `Authorization: Bearer <token>` and loads the user on every request (401 without a valid one; an empty `SECRET_KEY` rejects everyone). `require_admin` builds on it (403 for a user). Only `POST /v1/auth/login` and `/health` are open; conversations and the model list need a login, everything else an admin.

**Models** (`app/models/`): every model extends `AbstractModel` (`id`, `created_at`, `updated_at`). A schema change needs an Alembic migration in the same change.

**Config** (`app/config.py`): `Settings` is a Pydantic model whose fields are read from the upper-cased environment variable of the same name (`Settings.from_env()`); list fields (`MODELS`, `ALLOWED_ORIGINS`) are comma-separated there. Add new env vars here, to `env.example` and to the settings table in `readme.md`.

**Services** (`app/services/`):
- `user_service` — login, and the admin's list, create, update and delete of users. Services commit their own work. List queries go through `paginate` (`app/core/database.py`).
- `tag_service` — tags; deleting one takes it off every user, and is refused while a file still has it.
- `kb_service` — splits markdown pages into `Section`s by heading (the heading trail is kept, fenced code is not parsed for headings, hidden folders are skipped) and indexes them: `rebuild_index` for everything (only the reindex script calls it), `index_pages` for the pages an upload or delete touched. `list_pages` decides which files count as pages; listing, indexing and deleting all go through it. `page_tags` reads tag ids by page from the database, and every section is indexed with the tag ids of its page.
- `file_service` — lists, saves, tags and deletes pages in `KB_ROOT`. The folder decides which pages exist; a `File` row only holds a page's tags, so a page without a row is simply untagged. `import_files` (run by the script) adds the missing rows and copies the database's tags onto the index. Uploads are validated as a batch before any is written (`.md`, UTF-8, at most `MAX_UPLOAD_MB`), and only the file name of an upload is used, so nothing can be written outside the folder. A delete must match a listed page.
- `store_service` — `Store`, the only code that talks to Qdrant, bound to the one collection; `reset` drops it, `add` and `remove` change it a page at a time, `set_tags` relabels a page's sections without embedding, and `search` takes the tag ids to filter on (`None` for no limit).
- `llm_service` — `LLM`, the only code that talks to the model server: `embed` and `stream_chat`.
- `conversation_service` — `stream_answer` finds the sections closest to the new message among those the caller's tags allow (`search_tags`), builds the messages from the stored history and streams the reply, saving the message and its answer in a session of its own once the stream ends. Also the list, create, get, rename and delete of conversations.

### Conversation rules that must hold

- A client sends only its own new message (`MessageRequest` in `app/schemas/conversations.py`); the history is read from the database and the system prompt is always built on the server.
- A conversation belongs to one user. Every read and write goes through `get_conversation`, which reports someone else's conversation as missing (404); only admins reach other users' conversations.
- A message and its answer are saved together once the reply has streamed, so a failed reply leaves nothing behind. Creating a conversation saves no message; an untitled one takes its title from the first message.
- `KB_RULES` (`app/constants/prompts.py`) is appended to `SYSTEM_PROMPT`, with only the retrieved sections — never the whole knowledge base.
- A user's search is filtered by their tags inside the index query, never afterwards; a user gets untagged sections plus those sharing one of their tags, so a tag restricts a file and no tags opens it to everyone (sections indexed before tags existed count as untagged). Only admins search without a filter. Tags a request names can narrow this, never widen it, and leave the untagged sections out.
- Nothing may quietly leave a file untagged: a tag still on a file cannot be deleted (409).
- A file's tags live in the database and on its indexed sections. Anything that changes them updates both in the same request.
- Indexing and questions must use the same `EMBEDDING_MODEL`. Changing it means rebuilding the index (`scripts.reindex`).
- Everything a request needs to fail on (no login, unknown conversation, embedding the question) happens before the streaming response starts, so errors still return a proper status code.

## Conventions

- **New endpoint** = router in `app/api/` (registered in `app/main.py`) + Pydantic schemas in `app/schemas/` + logic in an `app/services/` function. No model, index or file access in routers.
- **Routes** declare a `response_model` (streaming routes excepted), and an explicit `status_code` when it isn't `200` (`201` on create, `204` on delete).
- **List endpoints are paginated** with `page` and `page_size` (`app/constants/pagination.py`) and reply with `total`, `page`, `page_size` and the items under the list's own name.
- **Anything that changes a knowledge base re-indexes the pages it changed** in the same request, so the files on disk and the index never disagree after an API call.
- **Who sees what is decided by tags only.** Don't branch on a tag's name, a user or a path; if a group needs its own content, that is a new tag.
- **Model calls stay on the OpenAI-compatible API** through `LLM`. Don't use Ollama-only endpoints or import a provider SDK elsewhere.
- **Settings and secrets** come from `app/config.py`; never hardcode what belongs in `.env`.
- **User-facing errors** raise `HTTPException` with a message the caller can act on, not internal detail.
- **Requirements document** (`docs/requirements.md`): when a change alters something it states — what the settings can hold, how indexing or chat behaves, what version 1 includes — update it in the same change. `readme.md` covers setup, the settings table and the endpoint table; keep those current too.

## Don't

- Don't add new dependencies without a clear need.
- Don't run `pip install` — update `requirements.txt` and rebuild.
- Don't introduce new architectural patterns when an existing one fits.
- Don't delete or rebuild Docker volumes (`ollama`, `qdrant`, `postgres`) unless asked.
- Don't run `scripts.reindex` to fix tags — it re-embeds everything; use `scripts.import_files`.
- Don't commit or push unless asked.
- Don't bypass or weaken the network guard in `tests/conftest.py`.
