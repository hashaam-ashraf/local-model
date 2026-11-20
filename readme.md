# local-model

A shared, self-hosted LLM service. Each project is a config file in `projects/`; the same deployment serves all of them. See `docs/requirements.md` for the scope.

```
browser or backend ──► api (FastAPI) ──► ollama   chat model + embedding model
                          │
                          ├──► qdrant            one collection per project
                          └──► data/chats.sqlite chat log
```

## Run

```bash
cp env.example .env                                    # set ADMIN_TOKEN
mkdir -p kb data                                       # so they belong to you, not to root
docker compose up -d --build
docker compose exec ollama ollama pull gemma3:4b       # DEFAULT_MODEL
docker compose exec ollama ollama pull bge-m3          # EMBEDDING_MODEL
```

Then give the project a knowledge base, in either way:

```bash
# upload markdown pages; they are indexed straight away
curl -X POST -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -F "files=@refunds.md" -F "files=@fees.md" http://localhost:8000/v1/tangerpay/files

# or check out a knowledge base repo and index it
git clone <kb repo url> kb/tangerpay-kb
curl -X POST -H "Authorization: Bearer <ADMIN_TOKEN>" http://localhost:8000/v1/tangerpay/index
```

Then open http://localhost:8000/?project=tangerpay and ask a question. The same endpoints can be tried at http://localhost:8000/docs (use **Authorize** with the admin token).

For a browser console that covers the whole flow — upload, delete, re-index and chat — run the sibling `local-model-frontend` repo (`docker compose up -d --build` there, then http://localhost:8080).

The images and the two models need roughly 8 GB of disk. On a GPU host, uncomment the `deploy` block in `docker-compose.yml` and set `DEFAULT_MODEL` to a larger model.

## Add a project

Create `projects/<slug>.toml` and restart the api:

```toml
name = "Acme"
system_prompt = "You are the Acme support assistant."
kb_path = "acme-kb"        # folder under kb/; leave out for a project with no knowledge base
model = "gemma3:12b"       # optional, defaults to DEFAULT_MODEL
models = ["gemma3:1b"]     # optional, other models a client may pick per request
top_k = 5                  # optional, sections given to the model per question
allowed_origins = ["https://acme.example"]   # optional, sites allowed to call the api from a browser
```

Then index it: `POST /v1/<slug>/index`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /v1/projects` | List the configured projects and the models each one allows, the default first |
| `POST /v1/<slug>/chat` | Body `{"messages": [{"role": "user", "content": "..."}]}`, plus an optional `"model"` from the project's list (an unknown name is a 422, another project's model a 400); the reply streams as plain text |
| `GET /v1/<slug>/files` | List the project's knowledge base pages |
| `POST /v1/<slug>/files` | Upload one or more markdown pages (multipart field `files`), then rebuild the index. A page with the same name is replaced |
| `DELETE /v1/<slug>/files/<path>` | Delete a page, then rebuild the index |
| `POST /v1/<slug>/index` | Rebuild the project's search index from its knowledge base folder, after changing files on disk |
| `GET /health` | Liveness check |

The `files` and `index` endpoints need `Authorization: Bearer <ADMIN_TOKEN>`. Uploads must be UTF-8 `.md` files of at most 5 MB each; they are saved in the top level of `kb/<kb_path>/`.

Backend jobs that only need a model can skip the api and use Ollama as an OpenAI-compatible endpoint at `http://127.0.0.1:11434/v1`.

To compare with a hosted model, point `LLM_BASE_URL`, `LLM_API_KEY` and `DEFAULT_MODEL` at it. Keep `EMBEDDING_MODEL` unchanged, or re-index.

## Tests

```bash
docker compose build api && docker compose run --rm --no-deps api pytest
```

The tests use a fake model and an in-memory index; they need no Ollama or Qdrant.

## Layout

```
app/
  main.py        App entrypoint: shared clients, CORS, router registration, demo page
  config.py      Settings from .env, projects from projects/*.toml
  api/           FastAPI routers (thin)
  schemas/       Pydantic request/response models
  services/      Logic: chat, knowledge base, model server, search index, chat log
  core/          FastAPI dependencies and the admin check
  constants/     Shared prompt rules and limits
  web/           Demo chat page
tests/
deploy/          Dockerfile
docs/            requirements.md
projects/        One TOML file per project
kb/              Knowledge base pages, one folder per project (not in git)
data/            Chat log (not in git)
```
