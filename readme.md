# local-model

A shared, self-hosted LLM service. Each project is a config file in `projects/`; the same deployment serves all of them. See `requirements.md` for the scope.

```
browser or backend ──► api (FastAPI) ──► ollama   chat model + embedding model
                          │
                          ├──► qdrant            one collection per project
                          └──► data/chats.sqlite chat log
```

## Run

```bash
cp .env.example .env                                   # set ADMIN_TOKEN
git clone <kb repo url> kb/tangerpay-kb                # one checkout per knowledge base
docker compose up -d --build
docker compose exec ollama ollama pull gemma3:4b       # DEFAULT_MODEL
docker compose exec ollama ollama pull bge-m3          # EMBEDDING_MODEL
curl -X POST -H "Authorization: Bearer <ADMIN_TOKEN>" http://localhost:8000/v1/tangerpay/index
```

Then open http://localhost:8000/?project=tangerpay.

The images and the two models need roughly 8 GB of disk. On a GPU host, uncomment the `deploy` block in `docker-compose.yml` and set `DEFAULT_MODEL` to a larger model.

## Add a project

Create `projects/<slug>.toml` and restart the api:

```toml
name = "Acme"
system_prompt = "You are the Acme support assistant."
kb_path = "acme-kb"        # folder under kb/; leave out for a project with no knowledge base
model = "gemma3:12b"       # optional, defaults to DEFAULT_MODEL
top_k = 5                  # optional, sections given to the model per question
allowed_origins = ["https://acme.example"]   # optional, sites allowed to call the api from a browser
```

Then index it: `POST /v1/<slug>/index`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /v1/projects` | List the configured projects |
| `POST /v1/<slug>/chat` | Body `{"messages": [{"role": "user", "content": "..."}]}`; the reply streams as plain text |
| `POST /v1/<slug>/index` | Rebuild the project's search index from its knowledge base; needs `Authorization: Bearer <ADMIN_TOKEN>` |
| `GET /health` | Liveness check |

Backend jobs that only need a model can skip the api and use Ollama as an OpenAI-compatible endpoint at `http://127.0.0.1:11434/v1`.

To compare with a hosted model, point `LLM_BASE_URL`, `LLM_API_KEY` and `DEFAULT_MODEL` at it. Keep `EMBEDDING_MODEL` unchanged, or re-index.

## Tests

```bash
docker compose build api && docker compose run --rm test
```

The tests use a fake model and an in-memory index; they need no Ollama or Qdrant.

## Layout

```
local_model/
  main.py      FastAPI app and endpoints
  config.py    Settings from .env, projects from projects/*.toml
  kb.py        markdown pages -> sections split by heading
  store.py     Qdrant: one collection per project
  llm.py       chat and embeddings over the OpenAI-compatible API
  chat.py      prompt building
  chatlog.py   SQLite log of questions and answers
  web/         demo chat page
projects/      one TOML file per project
kb/            knowledge base checkouts (not in git)
data/          chat log (not in git)
tests/
```
