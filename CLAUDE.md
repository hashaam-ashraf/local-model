# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with code in this repository.

## Project

A shared, self-hosted LLM service. Each project (the first is the Tangerpay support chat agent) is a TOML file in `projects/`; one deployment serves all of them. A project gets a streaming chat endpoint, optionally answering from a markdown knowledge base. Scope and open questions are in `docs/requirements.md`.

- **Framework:** FastAPI + Uvicorn
- **Schemas:** Pydantic v2
- **Model server:** Ollama, called only through the OpenAI-compatible API (`openai` client), so a hosted API can be swapped in by URL
- **Search index:** Qdrant, one collection per project
- **Chat log:** SQLite at `data/chats.sqlite`
- **No database, migrations or background jobs.**

The API is published on host port **8000**, bound to `127.0.0.1`. Routes are versioned under `/v1`.

## Layout

```
app/
  main.py        App entrypoint: create_app() builds the shared clients, CORS, router registration, demo page
  config.py      Settings (from the environment) and Project (from projects/*.toml)
  api/           FastAPI routers — thin
  schemas/       Pydantic request/response models (the API contract)
  services/      Logic — retrieval, prompt building, model calls, the search index, the chat log
  core/          Cross-cutting: FastAPI dependencies and the admin check
  constants/     Shared prompt rules and limits
  web/           Demo chat page (static, served at /)
tests/           pytest suite (harness in tests/conftest.py)
deploy/          Dockerfile
docs/            requirements.md — purpose, scope, later work, open questions
projects/        One TOML file per project
kb/              Knowledge base pages, one folder per project: checkouts or uploads (not in git)
data/            Chat log (not in git)
```

## Commands

There is **no local virtualenv** — run everything in Docker. `docker-compose.yml` is in this repo.

```bash
cp env.example .env                                    # set ADMIN_TOKEN
mkdir -p kb data                                       # otherwise Docker creates them as root and the api cannot write
docker compose up -d --build                           # api + ollama + qdrant
docker compose exec ollama ollama pull gemma3:4b       # DEFAULT_MODEL
docker compose exec ollama ollama pull bge-m3          # EMBEDDING_MODEL
curl -X POST -H "Authorization: Bearer <ADMIN_TOKEN>" -F "files=@page.md" http://localhost:8000/v1/<slug>/files
```

Uploading or deleting a page re-indexes the project. After changing files in `kb/` by hand (a git checkout, an edit), call `POST /v1/<slug>/index`.

The code is copied into the image, not mounted: **rebuild after a code change** (`docker compose up -d --build api`). `projects/`, `kb/` and `data/` are mounted, but project files are read once at startup, so restart the api after editing one.

Demo page at `/?project=<slug>`, Swagger at `/docs` (the **Authorize** button takes the admin token), health check at `/health`.

## Tests

```bash
docker compose build api && docker compose run --rm --no-deps api pytest
```

`--no-deps` keeps Ollama and Qdrant from starting; the tests don't need them. The compose file requires `.env` to exist.

Tests build the app with `create_app(settings, llm, store)`, passing a `FakeLLM` and a `Store` over `QdrantClient(":memory:")` (the `env` fixture in `tests/conftest.py`). `tests/conftest.py` blocks every socket connection, so a test that reaches a real model server or index fails.

When writing tests:
- Inject fakes through `create_app`; never loosen the network guard to make a test pass.
- Point `Settings` at `tmp_path` for `projects_dir`, `kb_root` and `chat_log`, so nothing touches the real folders.
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
app/services/*   Logic. Every model, index, file and chat-log call lives here.
```

**App wiring** (`app/main.py`): `create_app()` is a factory (Uvicorn runs it with `--factory`). It loads settings and projects, builds one `LLM` and one `Store`, and puts all four on `app.state`. Routers register with the `/v1` prefix; the chat router is built by `create_router(models)`, so the request's `model` field is an enum of every model the project files allow; `/health` and the static demo page are mounted at the root. CORS allows the union of every project's `allowed_origins`. There is no module-level `app` or `settings` singleton — that is what lets tests pass in fakes.

**Dependencies** (`app/core/dependencies.py`): routers reach the shared objects only through `get_settings`, `get_llm`, `get_store`, `get_projects` and `get_project` (resolves the `{slug}` path parameter, 404 for an unknown one). `require_admin` checks `Authorization: Bearer <ADMIN_TOKEN>`; an empty `ADMIN_TOKEN` rejects everyone. Every endpoint that reads or changes a knowledge base is behind it.

**Config** (`app/config.py`): `Settings` is a Pydantic model whose fields are read from the upper-cased environment variable of the same name (`Settings.from_env()`). `Project` is the shape of a `projects/<slug>.toml` file; the slug is the file name. Add new env vars here and to `env.example`; add new project options to `Project` and to the example in `readme.md`.

**Services** (`app/services/`):
- `kb_service` — splits markdown pages into `Section`s by heading (the heading trail is kept, fenced code is not parsed for headings, hidden folders are skipped) and rebuilds a project's index. `list_pages` decides which files count as pages; listing, indexing and deleting all go through it.
- `file_service` — lists, saves and deletes pages in `kb/<kb_path>/`. Uploads are validated as a batch before any is written (`.md`, UTF-8, at most `MAX_UPLOAD_MB`), and only the file name of an upload is used, so nothing can be written outside the folder. A delete must match a listed page.
- `store_service` — `Store`, the only code that talks to Qdrant. One collection per project, named by slug; `replace` drops and rebuilds it.
- `llm_service` — `LLM`, the only code that talks to the model server: `embed` and `stream_chat`.
- `chat_service` — finds the sections closest to the latest question, builds the messages and streams the reply, saving it to the chat log once the stream ends.
- `chatlog_service` — appends a row to SQLite.

### Chat rules that must hold

- A client may send only `user` and `assistant` messages (`app/schemas/chat.py`); the system prompt is always built on the server.
- A project with a knowledge base gets the shared `KB_RULES` (`app/constants/prompts.py`) appended to its own prompt, and only the retrieved sections — never the whole knowledge base.
- Projects never see each other's content: every search and index call is scoped by the project slug.
- Indexing and questions must use the same `EMBEDDING_MODEL`. Changing it means re-indexing every project.
- Everything a request needs to fail on (unknown project, bad history, embedding the question) happens before the streaming response starts, so errors still return a proper status code.

## Conventions

- **New endpoint** = router in `app/api/` (registered in `app/main.py`) + Pydantic schemas in `app/schemas/` + logic in an `app/services/` function. No model, index or file access in routers.
- **Routes** declare a `response_model` (streaming routes excepted), and an explicit `status_code` when it isn't `200` (`201` on upload, `204` on delete).
- **Anything that changes a knowledge base re-indexes it** in the same request, so the files on disk and the index never disagree after an API call.
- **Adding a project must not need a code change.** Per-project behaviour belongs in the TOML file; if a project needs something new, make it an option on `Project`, not a branch on the slug.
- **Model calls stay on the OpenAI-compatible API** through `LLM`. Don't use Ollama-only endpoints or import a provider SDK elsewhere.
- **Settings and secrets** come from `app/config.py`; never hardcode what belongs in `.env`.
- **User-facing errors** raise `HTTPException` with a message the caller can act on, not internal detail.
- **Requirements document** (`docs/requirements.md`): when a change alters something it states — what a project file can hold, how indexing or chat behaves, what version 1 includes — update it in the same change. `readme.md` covers setup, the project file format and the endpoint table; keep those current too.

## Don't

- Don't add new dependencies without a clear need.
- Don't run `pip install` — update `requirements.txt` and rebuild.
- Don't introduce new architectural patterns when an existing one fits.
- Don't delete or rebuild Docker volumes (`ollama`, `qdrant`) or `data/` unless asked.
- Don't commit or push unless asked.
- Don't bypass or weaken the network guard in `tests/conftest.py`.
