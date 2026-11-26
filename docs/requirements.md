# Requirements

## Purpose

One self-hosted assistant that answers from our own documents without sending data to OpenAI or ElevenLabs. People log in, and each one gets answers only from the documents they are allowed to see. The first knowledge base is the Tangerpay support content.

## Goals

1. Run open-weight models on hardware we control, behind one service.
2. One assistant and one knowledge base, with tags deciding which files each user's answers may come from.
3. Keep every model call on the OpenAI-compatible API, so the service can be pointed at OpenAI or at the local model by changing a URL and a model name.
4. Giving a new group of users their own content must not need a code change: it is a tag.

## How it is used

| Need | How |
|---|---|
| A chat that answers from the knowledge base | Log in, call `POST /v1/conversations`, then `POST /v1/conversations/<id>/messages` |
| Content only some users may see | Give the files and those users the same tag |
| Raw model access from a backend job | Call the Ollama endpoint directly as an OpenAI-compatible API |

## Functional requirements

### Assistant settings

- One system prompt, one default model, an optional list of other models a request may choose, the number of sections to retrieve and the allowed browser origins, all set in the environment.
- A request may name a model from the list; any other model is rejected. Without one, the default model is used.

### Knowledge base indexing

- Read the markdown pages of the knowledge base from one folder on the server. The folder is filled by uploading pages or by checking out a repo.
- List, upload, tag and delete pages through endpoints only an admin can call. An upload or a delete updates the index for those pages only, so the next question already uses it.
- Split each page by heading; one section is one searchable unit.
- Convert each section to a vector with the embedding model and store it in the search index, with the tags of its page.
- A full rebuild of the index is a script, not an endpoint. It is needed only after editing pages on disk by hand or changing the embedding model, and keeps each page's tags.
- Indexing and questions must use the same embedding model. Changing the model means rebuilding the index.

### Users and tags

- Everyone logs in with an email and password and gets a token; only login and the health check work without one.
- Two roles: an admin can do everything, a user can only chat. Admins create, change and delete users. The first admin is created when the service starts, from an email and password in the environment.
- A tag is a label with a name and an optional description. A file can have several tags, and so can a user.
- A file without tags is open to every user. A file with tags is used only for users who hold at least one of them, and for admins, who are not limited by tags.
- A tag cannot be deleted while a file still has it, since that would open the file to everyone.
- A change to a user's tags or a file's tags applies from the next question. Changing a file's tags does not index it again.
- Pages already on disk are added to the database by a script, not by indexing them again.
- The lists of users, tags and files are returned a page at a time.

### Chat

- A conversation belongs to the user who created it and is stored with all its messages. It is created empty, then messages are sent to it. The caller sends only the new message and the reply is streamed; the earlier messages are read from the database.
- A user can list, read, rename and delete their own conversations. An admin can do the same with anyone's. Deleting a user deletes their conversations.
- A request may name some of the caller's tags to search only those; it can never reach files the caller's own tags do not.
- Find the sections closest to the latest question among those the caller may see, and give the model only those sections, the system prompt and the conversation.
- The model must answer only from those sections. When they do not contain the answer it says so and offers a handoff to a person.
- A client can never send system instructions or earlier messages; it sends only its own new message.
- Each answer is saved with the sections it was given, for review. A message and its answer are saved once the reply has finished, so a failed reply leaves nothing behind.

## Non-functional requirements

- **Privacy:** questions, answers and knowledge base content stay on our server. No call leaves it unless the service is deliberately pointed at a hosted API.
- **Hosting:** everything runs with Docker Compose on one server. Only the LLM needs a GPU; the API, the embedding model and the search index run on CPU.
- **Development machine:** a small model on CPU is enough to prove the flow. Speed and answer quality are judged on a GPU server.
- **Tests:** run without a network, a model server or a search server.

## Version 1 scope

- Endpoints to list, upload, tag and delete knowledge base pages; uploads and deletes index only the pages they touch.
- An admin seeded at startup, and scripts to add pages already on disk to the database and rebuild the index.
- Streaming chat endpoint with retrieval.
- Conversations stored per user, with endpoints to list, read, rename and delete them.
- Users with two roles, logins, and tags that limit which files a user's answers come from.
- Docker Compose with the API, Ollama, Qdrant and Postgres.

## Later

- Pull a knowledge base repo automatically after each merge, and re-index only the pages it changed.
- Hybrid search (keywords plus vectors), for exact terms such as product names and error codes.
- An embeddable widget for customer sites, with rate limiting.
- Handoff to a person (ticket or live agent).
- A test set of real questions, run against both the local model and OpenAI.
- Access keys for backend callers.
- Voice (speech-to-text and text-to-speech).

## Open questions

- Which GPU host, and must customer conversations stay in a particular country?
- Which languages must the Tangerpay agent handle? This decides whether the default embedding model is enough.
- Which model size is good enough? To be decided with the test set on a GPU.
- Can the Tangerpay KB drafting job use the local model? It relies on the OpenAI Responses API with strict structured output, which needs testing against Ollama.
- Model server image versions are not pinned yet; pin them before production.
