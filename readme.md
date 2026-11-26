# local-model

A self-hosted LLM assistant that answers from a markdown knowledge base. Users log in, and each one gets answers only from the files that share a tag with them. See `docs/requirements.md` for the scope.

```
browser or backend ──► api (FastAPI) ──► ollama   chat model + embedding model
                          │
                          ├──► qdrant            the search index
                          └──► postgres          users, tags, the tags of each file, conversations
```

## Run

```bash
cp env.example .env                                    # set SECRET_KEY, ADMIN_EMAIL and ADMIN_PASSWORD; the rest is optional
mkdir -p kb                                            # so it belongs to you, not to root
docker compose up -d --build                           # scripts/init.sh creates the database, applies the migrations and creates the admin before the api starts
docker compose exec ollama ollama pull gemma3:4b       # DEFAULT_MODEL
docker compose exec ollama ollama pull bge-m3          # EMBEDDING_MODEL
```

On a CPU-only host Ollama may use only a couple of threads. Setting the thread count on a model, under the same name, roughly doubles its speed; repeat it after each `ollama pull` of that model:

```bash
docker compose exec ollama sh -c 'printf "FROM gemma3:4b\nPARAMETER num_thread 10\n" > /tmp/Modelfile && ollama create gemma3:4b -f /tmp/Modelfile'
```

Log in to get a token; every other endpoint needs it as `Authorization: Bearer <token>`:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "..."}' http://localhost:8000/v1/auth/login
```

Then create a tag and upload markdown pages with it; they are indexed straight away:

```bash
curl -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name": "billing", "description": "Fees, refunds and invoices"}' http://localhost:8000/v1/tags

curl -X POST -H "Authorization: Bearer <token>" \
  -F "files=@refunds.md" -F "files=@fees.md" -F "tags=<tag id>" http://localhost:8000/v1/files
```

Every endpoint can be tried at http://localhost:8000/docs (use **Authorize** with the token).

The images and the two models need roughly 8 GB of disk. On a GPU host, uncomment the `deploy` block in `docker-compose.yml` and set `DEFAULT_MODEL` to a larger model.

## Settings

All in `.env` (see `env.example`); restart the api after a change.

| Variable | Purpose |
|---|---|
| `SYSTEM_PROMPT` | Who the assistant is. The knowledge base rules are added to it on the server |
| `DEFAULT_MODEL`, `MODELS` | The model used for chat, and a comma-separated list of others a request may name |
| `TOP_K` | Sections given to the model per question (5 by default) |
| `ALLOWED_ORIGINS` | Comma-separated sites allowed to call the api from a browser |
| `KB_ROOT`, `COLLECTION` | The folder of pages and the Qdrant collection that indexes it |
| `EMBEDDING_MODEL` | Must be the same for indexing and questions; changing it means `python -m scripts.reindex` |
| `SECRET_KEY` | Signs login tokens; nobody can log in while it is empty |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | The admin created when the api starts, if no user has that email yet. An existing account is never changed, so change the password through the api |

## Users and tags

There are two roles. An **admin** can do everything. A **user** can only hold conversations, sees only their own, and gets answers only from files that share a tag with them: a file with no tags, or a user with no tags, matches nothing. Admins are not limited by tags.

Create tags with `POST /v1/tags`, give them to a user when creating or updating the user, and to a file when uploading it or with `PUT /v1/files/<path>`. A change applies from the next question; changing a file's tags relabels its sections in the index without indexing it again.

## Pages that did not come through the api

Pages that are in `KB_ROOT` but not in the database (indexed before tags existed, or added by a git checkout) are added by a script, which does not index anything again:

```bash
docker compose exec api python -m scripts.import_files --tag docs   # --tag is optional and repeatable
```

Only the pages it adds get the tags. It then copies the tags in the database onto the index, so it is also the repair if the two ever disagree, and it is safe to repeat.

Pages whose text was edited on disk, or a changed `EMBEDDING_MODEL`, need the index rebuilt. This embeds every page again and takes hours for a large knowledge base:

```bash
docker compose exec api python -m scripts.reindex
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /v1/auth/login` | Body `{"email": "...", "password": "..."}`; the reply holds the `token`, valid for 12 hours |
| `GET /v1/auth/me` | The logged-in user, with their role and tags |
| `GET /v1/models` | The models a message may name, the default first |
| `POST /v1/conversations` | Create an empty conversation. The body is optional: `{"title": "..."}`; without a title, the first message gives it one |
| `POST /v1/conversations/<id>/messages` | Send a message. Body `{"message": "..."}`, plus an optional `"model"` from the list (anything else is a 422) and optional `"tags"` (tag ids) to search only those of the caller's tags. The reply streams as plain text. The earlier messages are read on the server, so the client sends only the new one |
| `GET /v1/conversations` | The caller's conversations, newest first (`id`, `user_id`, `title`, `created_at`). An admin gets everyone's |
| `GET /v1/conversations/<id>` | One conversation with its `messages`; each answer lists the `sources` it was given |
| `PATCH /v1/conversations/<id>`, `DELETE /v1/conversations/<id>` | Rename a conversation (body `{"title": "..."}`); delete it with its messages |
| `GET /v1/users`, `POST /v1/users` | Admin. List users; create one from `email`, `name`, `password` (8 to 72 characters), `role` (`user` by default, or `admin`) and `tags` (tag ids) |
| `PATCH /v1/users/<id>`, `DELETE /v1/users/<id>` | Admin. Change a user's `name`, `password`, `role` or `tags` (only the fields sent); delete a user |
| `GET /v1/tags`, `POST /v1/tags`, `DELETE /v1/tags/<id>` | Admin. List tags, create one from a `name` and an optional `description`, delete one (it is taken off every user and file) |
| `GET /v1/files` | Admin. List the knowledge base pages with their tags |
| `POST /v1/files` | Admin. Upload one or more markdown pages (multipart field `files`, and `tags` once per tag id) and index them. A page with the same name is replaced, tags included; `sections` in the reply counts the sections of the uploaded pages |
| `PUT /v1/files/<path>` | Admin. Body `{"tags": [...]}` replaces a page's tags |
| `DELETE /v1/files/<path>` | Admin. Delete a page and remove it from the index |
| `GET /health` | Liveness check |

Everything except `login` and `health` needs `Authorization: Bearer <token>`; a missing or expired token is a 401, a user calling an admin endpoint a 403.

The four lists (`users`, `tags`, `files`, `conversations`) come 50 at a time: `?page=2&page_size=50` (at most 200). The reply holds `total`, `page`, `page_size` and the items under the list's own name.

Uploads must be UTF-8 `.md` files of at most 5 MB each; they are saved in the top level of `KB_ROOT`.

Backend jobs that only need a model can skip the api and use Ollama as an OpenAI-compatible endpoint at `http://127.0.0.1:11434/v1`.

To compare with a hosted model, point `LLM_BASE_URL`, `LLM_API_KEY` and `DEFAULT_MODEL` at it. Keep `EMBEDDING_MODEL` unchanged, or re-index.

## Tests

```bash
docker compose build api && docker compose run --rm --no-deps api pytest
```

The tests use a fake model, an in-memory index and a SQLite database; they need no Ollama, Qdrant or Postgres.

## Layout

```
app/
  main.py        App entrypoint: shared clients, CORS, router registration
  config.py      Settings from .env
  api/           FastAPI routers (thin)
  schemas/       Pydantic request/response models
  models/        SQLAlchemy models: users, tags, files, conversations and their messages
  services/      Logic: conversations, knowledge base, users, tags, model server, search index
  core/          FastAPI dependencies, the login check, database and password helpers
  constants/     Shared prompt rules and limits
tests/
alembic/         Database migrations
scripts/         init.sh, create_database, seed_admin, import_files, reindex
deploy/          Dockerfile
docs/            requirements.md
kb/              Knowledge base pages (not in git)
```
