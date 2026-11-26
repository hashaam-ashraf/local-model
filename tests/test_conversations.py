REFUND = "How long does a refund take?"


def send(client, conversation_id, text, headers=None):
    return client.post(f"/v1/conversations/{conversation_id}/messages", json={"message": text}, headers=headers)


def start(client, text, headers=None):
    """Create a conversation and send its first message."""
    conversation_id = client.post("/v1/conversations", headers=headers).json()["id"]
    assert send(client, conversation_id, text, headers).status_code == 200
    return conversation_id


def titles(client, headers=None, query=""):
    body = client.get(f"/v1/conversations?{query}", headers=headers).json()
    return body["total"], sorted(c["title"] for c in body["conversations"])


def test_conversation_is_saved_with_its_messages(env, reindex):
    client, _, _ = env
    reindex()
    me = client.get("/v1/auth/me").json()["id"]

    conversation = client.get(f"/v1/conversations/{start(client, REFUND)}").json()

    assert (conversation["user_id"], conversation["title"]) == (me, REFUND)
    assert [(m["role"], m["content"], m["sources"]) for m in conversation["messages"]] == [
        ("user", REFUND, None),
        ("assistant", "Hello there", ["money.md | Refunds"]),
    ]


def test_next_message_continues_the_conversation_from_the_stored_history(env):
    client, llm, _ = env
    conversation_id = start(client, "Hi")

    assert send(client, conversation_id, "And the fee?").text == "Hello there"
    assert llm.chats[-1][1][1:] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello there"},
        {"role": "user", "content": "And the fee?"},
    ]
    assert llm.embedded[-1] == "And the fee?"
    messages = client.get(f"/v1/conversations/{conversation_id}").json()["messages"]
    assert [m["content"] for m in messages] == ["Hi", "Hello there", "And the fee?", "Hello there"]
    assert titles(client) == (1, ["Hi"])


def test_only_the_latest_messages_are_given_to_the_model(env):
    client, llm, _ = env
    conversation_id = start(client, "Question 0")
    for n in range(1, 12):
        send(client, conversation_id, f"Question {n}")

    history = llm.chats[-1][1][1:]
    assert len(history) == 20
    assert (history[1]["content"], history[-1]["content"]) == ("Question 2", "Question 11")


def test_create_conversation_saves_no_message(env):
    client, llm, _ = env
    me = client.get("/v1/auth/me").json()["id"]

    res = client.post("/v1/conversations")

    assert res.status_code == 201
    assert (res.json()["user_id"], res.json()["title"]) == (me, None)
    assert client.get(f"/v1/conversations/{res.json()['id']}").json()["messages"] == []
    assert (llm.chats, llm.embedded) == ([], [])
    assert client.post("/v1/conversations", json={"title": ""}).status_code == 422


def test_untitled_conversation_is_titled_by_its_first_message(env):
    client, _, _ = env
    conversation_id = start(client, "x" * 200)
    send(client, conversation_id, "Second message")
    assert client.get(f"/v1/conversations/{conversation_id}").json()["title"] == "x" * 80

    named = client.post("/v1/conversations", json={"title": "Refunds"}).json()
    send(client, named["id"], "Hi")
    assert client.get(f"/v1/conversations/{named['id']}").json()["title"] == "Refunds"


def test_users_see_only_their_own_conversations(env, as_user):
    client, llm, _ = env
    ann, bob = as_user("ann@example.com"), as_user("bob@example.com")
    mine = start(client, "Admin question")
    hers = start(client, "Ann question", ann)
    start(client, "Bob question", bob)

    assert titles(client, ann) == (1, ["Ann question"])
    assert titles(client, bob) == (1, ["Bob question"])
    assert titles(client) == (3, ["Admin question", "Ann question", "Bob question"])

    asked = len(llm.chats)
    for other in [hers, mine]:
        assert client.get(f"/v1/conversations/{other}", headers=bob).status_code == 404
        assert send(client, other, "Hi", bob).status_code == 404
        assert client.patch(f"/v1/conversations/{other}", json={"title": "x"}, headers=bob).status_code == 404
        assert client.delete(f"/v1/conversations/{other}", headers=bob).status_code == 404
    assert len(llm.chats) == asked
    assert client.get(f"/v1/conversations/{hers}").json()["title"] == "Ann question"
    assert client.get(f"/v1/conversations/{hers}", headers={"Authorization": ""}).status_code == 401


def test_rename_and_delete(env, as_user):
    client, _, _ = env
    ann = as_user("ann@example.com")
    conversation_id = start(client, "Old title", ann)

    renamed = client.patch(f"/v1/conversations/{conversation_id}", json={"title": "New title"}, headers=ann)
    assert renamed.json()["title"] == "New title"
    assert client.patch(f"/v1/conversations/{conversation_id}", json={"title": ""}, headers=ann).status_code == 422

    assert client.delete(f"/v1/conversations/{conversation_id}", headers=ann).status_code == 204
    assert client.get(f"/v1/conversations/{conversation_id}", headers=ann).status_code == 404
    assert titles(client) == (0, [])
    missing = "00000000-0000-0000-0000-000000000000"
    assert send(client, missing, "Hi").status_code == 404


def test_conversations_are_listed_in_pages(env):
    client, _, _ = env
    for n in range(3):
        start(client, f"Question {n}")

    first = client.get("/v1/conversations?page_size=2").json()
    second = client.get("/v1/conversations?page=2&page_size=2").json()
    assert (first["total"], len(first["conversations"]), len(second["conversations"])) == (3, 2, 1)
    shown = [c["title"] for c in first["conversations"] + second["conversations"]]
    assert sorted(shown) == ["Question 0", "Question 1", "Question 2"]
    assert client.get("/v1/conversations?page_size=201").status_code == 422


def test_deleting_a_user_deletes_their_conversations(env, as_user):
    client, _, _ = env
    ann = as_user("ann@example.com")
    conversation_id = start(client, "Ann question", ann)
    user_id = client.get("/v1/auth/me", headers=ann).json()["id"]

    assert client.delete(f"/v1/users/{user_id}").status_code == 204

    assert titles(client) == (0, [])
    assert client.get(f"/v1/conversations/{conversation_id}").status_code == 404
