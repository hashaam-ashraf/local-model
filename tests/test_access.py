"""A user's answers come from untagged files and from files that share one of their tags."""

from app.services import file_service

CARDS = ("cards.md", b"# Cards\n\nA card arrives in 3 days.\n")
REFUND = "How long does a refund take?"


def tag_id(client, name):
    return next(tag["id"] for tag in client.get("/v1/tags").json()["tags"] if tag["name"] == name)


def upload(client, file, *tags):
    return client.post("/v1/files", files=[("files", file)], data={"tags": [tag_id(client, t) for t in tags]})


def given(client, llm, headers, text, **extra):
    """The system prompt the model got for this question."""
    conversation_id = client.post("/v1/conversations", headers=headers).json()["id"]
    send = client.post(
        f"/v1/conversations/{conversation_id}/messages", json={"message": text, **extra}, headers=headers
    )
    assert send.status_code == 200
    return llm.chats[-1][1][0]["content"]


def test_untagged_files_are_for_everyone(env, as_user, reindex):
    client, llm, _ = env
    reindex()

    for headers in [client.headers, as_user("u@example.com", "billing"), as_user("none@example.com")]:
        assert "A refund takes 5 days." in given(client, llm, headers, REFUND)


def test_user_without_the_tag_gets_nothing_from_a_tagged_file(env, as_user, reindex):
    client, llm, _ = env
    other, none = as_user("o@example.com", "other"), as_user("none@example.com")
    client.post("/v1/tags", json={"name": "billing"})
    client.put("/v1/files/money.md", json={"tags": [tag_id(client, "billing")]})
    reindex()

    assert "A refund takes 5 days." in given(client, llm, client.headers, REFUND)
    for headers in [other, none]:
        assert "(no section matched this question)" in given(client, llm, headers, REFUND)


def test_user_gets_only_files_with_one_of_their_tags(env, as_user, reindex):
    client, llm, _ = env
    billing, cards = as_user("b@example.com", "billing"), as_user("c@example.com", "cards", "other")
    reindex()
    assert upload(client, CARDS, "cards").status_code == 201
    client.put("/v1/files/money.md", json={"tags": [tag_id(client, "billing")]})

    assert "A refund takes 5 days." in given(client, llm, billing, REFUND)
    # The closest section is not theirs, so the search moves on to one that is.
    system = given(client, llm, cards, REFUND)
    assert "A refund takes 5 days." not in system
    assert "A card arrives in 3 days." in system


def test_changing_file_tags_applies_to_the_next_question_without_embedding(env, as_user, reindex):
    client, llm, _ = env
    user = as_user("u@example.com", "billing")
    reindex()
    embedded = len(llm.embedded)

    res = client.put("/v1/files/money.md", json={"tags": [tag_id(client, "billing")]})
    assert [tag["name"] for tag in res.json()["tags"]] == ["billing"]
    assert client.get("/v1/files").json()["files"][0]["tags"] == res.json()["tags"]
    assert len(llm.embedded) == embedded
    assert "A refund takes 5 days." in given(client, llm, user, REFUND)

    client.post("/v1/tags", json={"name": "other"})
    client.put("/v1/files/money.md", json={"tags": [tag_id(client, "other")]})
    assert "A refund takes 5 days." not in given(client, llm, user, REFUND)

    client.put("/v1/files/money.md", json={"tags": []})
    assert "A refund takes 5 days." in given(client, llm, user, REFUND)

    assert client.put("/v1/files/missing.md", json={"tags": []}).status_code == 404
    unknown = "00000000-0000-0000-0000-000000000000"
    assert client.put("/v1/files/money.md", json={"tags": [unknown]}).status_code == 400


def test_changing_user_tags_applies_to_the_next_question(env, as_user, reindex):
    client, llm, _ = env
    user = as_user("u@example.com", "billing")
    user_id = client.get("/v1/auth/me", headers=user).json()["id"]
    client.put("/v1/files/money.md", json={"tags": [tag_id(client, "billing")]})
    reindex()
    assert "A refund takes 5 days." in given(client, llm, user, REFUND)

    client.patch(f"/v1/users/{user_id}", json={"tags": []})
    assert "A refund takes 5 days." not in given(client, llm, user, REFUND)



def test_tag_on_a_file_cannot_be_deleted(env, as_user, reindex):
    """Deleting it would leave the file untagged, and so open to every user."""
    client, llm, _ = env
    user = as_user("u@example.com", "other")
    client.post("/v1/tags", json={"name": "billing"})
    billing = tag_id(client, "billing")
    client.put("/v1/files/money.md", json={"tags": [billing]})
    reindex()

    res = client.delete(f"/v1/tags/{billing}")
    assert res.status_code == 409
    assert "still on 1 file" in res.json()["detail"]
    assert "A refund takes 5 days." not in given(client, llm, user, REFUND)

    client.post("/v1/tags", json={"name": "internal"})
    client.put("/v1/files/money.md", json={"tags": [tag_id(client, "internal")]})
    assert client.delete(f"/v1/tags/{billing}").status_code == 204
    assert "A refund takes 5 days." not in given(client, llm, user, REFUND)


def test_requested_tags_narrow_the_search_but_never_widen_it(env, as_user, reindex):
    client, llm, _ = env
    user = as_user("u@example.com", "billing")
    client.post("/v1/tags", json={"name": "cards"})
    billing, cards = tag_id(client, "billing"), tag_id(client, "cards")
    client.put("/v1/files/money.md", json={"tags": [billing]})
    reindex()
    upload(client, CARDS, "cards")
    upload(client, ("limits.md", b"# Limits\n\nThe daily limit is 500.\n"))

    # Without named tags the untagged page is searched too; naming tags leaves it out.
    assert "The daily limit is 500." in given(client, llm, user, "What is the limit?")
    assert "The daily limit is 500." not in given(client, llm, user, "What is the limit?", tags=[billing])
    assert "A refund takes 5 days." in given(client, llm, user, REFUND, tags=[billing])
    assert "(no section matched this question)" in given(client, llm, user, REFUND, tags=[cards])
    assert "A card arrives in 3 days." in given(client, llm, client.headers, REFUND, tags=[cards])


def test_upload_and_rebuild_keep_tags(env, as_user, reindex):
    client, llm, _ = env
    user, other = as_user("u@example.com", "cards"), as_user("o@example.com", "other")
    question = "When does my card arrive?"
    assert upload(client, CARDS, "cards").status_code == 201
    assert "A card arrives in 3 days." in given(client, llm, user, question)
    assert "A card arrives in 3 days." not in given(client, llm, other, question)

    reindex()
    assert "A card arrives in 3 days." in given(client, llm, user, question)
    assert "A card arrives in 3 days." not in given(client, llm, other, question)

    # Uploading again without tags replaces them, which opens the page to everyone; deleting forgets them.
    upload(client, CARDS)
    assert "A card arrives in 3 days." in given(client, llm, other, question)
    upload(client, CARDS, "cards")
    assert "A card arrives in 3 days." not in given(client, llm, other, question)
    client.delete("/v1/files/cards.md")
    upload(client, CARDS)
    assert client.get("/v1/files").json()["files"][0] == {"path": "cards.md", "size": 35, "tags": []}

    unknown = "00000000-0000-0000-0000-000000000000"
    bad = client.post("/v1/files", files=[("files", ("new.md", b"# N\n\nText."))], data={"tags": [unknown]})
    assert bad.status_code == 400
    assert client.get("/v1/files").json()["total"] == 2


def test_import_adds_existing_pages_without_embedding(env, as_user, reindex):
    client, llm, settings = env
    user = as_user("u@example.com", "billing")
    reindex()
    embedded = len(llm.embedded)
    state = client.app.state

    with state.sessions() as db:
        assert file_service.import_files(settings, db, state.store, ["billing", "docs"]) == 1
        assert file_service.import_files(settings, db, state.store, ["other"]) == 0

    assert len(llm.embedded) == embedded
    tags = client.get("/v1/files").json()["files"][0]["tags"]
    assert sorted(tag["name"] for tag in tags) == ["billing", "docs"]
    assert "A refund takes 5 days." in given(client, llm, user, REFUND)
    assert "A refund takes 5 days." not in given(client, llm, as_user("o@example.com", "other"), REFUND)
