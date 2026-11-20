# Requirements

## Purpose

One self-hosted service that gives our projects an LLM without sending data to OpenAI or ElevenLabs. It is shared: each project is a config file, not a fork of the code. The first project is the Tangerpay support chat agent, which answers from the `tangerpay-kb` knowledge base.

## Goals

1. Run open-weight models on hardware we control, behind one service.
2. Serve several projects from the same deployment, each with its own prompt, model and optional knowledge base.
3. Keep every model call on the OpenAI-compatible API, so a project can be pointed at OpenAI or at the local model by changing a URL and a model name.
4. Adding a project must not need a code change.

## How projects use it

| Need | How |
|---|---|
| A chat agent that answers from a knowledge base | Add `projects/<name>.toml` with a `kb_path`, index it, call `POST /v1/<name>/chat` |
| A chat agent with only a prompt | Add `projects/<name>.toml` without `kb_path` |
| Raw model access from a backend job | Call the Ollama endpoint directly as an OpenAI-compatible API |

## Functional requirements

### Projects

- A project is one TOML file: display name, system prompt, optional model, optional list of other models a client may choose, optional knowledge base folder, number of sections to retrieve, allowed browser origins.
- A project without its own model uses the service default.
- A request may name a model from the project's list; any other model is rejected. Without one, the project's model is used.
- Each project's knowledge base is indexed into its own collection, so projects never see each other's content.

### Knowledge base indexing

- Read the markdown pages of a project's knowledge base from a folder on the server. The folder is filled by checking out a repo or by uploading pages.
- List, upload and delete pages through endpoints protected by an admin token. An upload or a delete rebuilds the index, so the next question already uses it.
- Split each page by heading; one section is one searchable unit.
- Convert each section to a vector with the embedding model and store it in the search index.
- Indexing can also be triggered on its own, through an endpoint protected by the same admin token.
- Indexing and questions must use the same embedding model. Changing the model means re-indexing every project.

### Chat

- Accept the conversation so far and stream the reply.
- For a project with a knowledge base: find the sections closest to the latest question and give the model only those sections, the project's prompt and the conversation.
- The model must answer only from those sections. When they do not contain the answer it says so and offers a handoff to a person.
- A browser client can send only user and assistant messages, never system instructions.
- Save each question, answer and the sections used, for review.

### Demo page

- A plain chat page served by the service, to try any project in a browser, with a model picker when the project allows more than one.

## Non-functional requirements

- **Privacy:** questions, answers and knowledge base content stay on our server. No call leaves it unless a project is deliberately pointed at a hosted API.
- **Hosting:** everything runs with Docker Compose on one server. Only the LLM needs a GPU; the API, the embedding model and the search index run on CPU.
- **Development machine:** a small model on CPU is enough to prove the flow. Speed and answer quality are judged on a GPU server.
- **Tests:** run without a network, a model server or a search server.

## Version 1 scope

- Project config files, with Tangerpay as the first.
- Endpoints to list, upload and delete knowledge base pages.
- Indexing endpoint (full rebuild of a project's index each time).
- Streaming chat endpoint with retrieval.
- Chat log in SQLite.
- Demo chat page.
- Docker Compose with the API, Ollama and Qdrant.

## Later

- Pull a knowledge base repo automatically after each merge, and re-index only the changed pages.
- Hybrid search (keywords plus vectors), for exact terms such as product names and error codes.
- An embeddable widget for customer sites, with rate limiting.
- Handoff to a person (ticket or live agent).
- A test set of real questions per project, run against both the local model and OpenAI.
- Per-project access keys for backend callers.
- Voice (speech-to-text and text-to-speech) for projects that need it.

## Open questions

- Which GPU host, and must customer conversations stay in a particular country?
- Which languages must the Tangerpay agent handle? This decides whether the default embedding model is enough.
- Which model size is good enough? To be decided with the test set on a GPU.
- Can the Tangerpay KB drafting job use the local model? It relies on the OpenAI Responses API with strict structured output, which needs testing against Ollama.
- Model server image versions are not pinned yet; pin them before production.
