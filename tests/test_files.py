ANON = {"Authorization": ""}


def upload(client, *files):
    return client.post("/v1/files", files=[("files", (name, content)) for name, content in files])


def ask(client, text):
    conversation_id = client.post("/v1/conversations").json()["id"]
    return client.post(f"/v1/conversations/{conversation_id}/messages", json={"message": text})


def test_files_require_an_admin(env, as_user):
    client, _, _ = env
    for headers, status in [(ANON, 401), (as_user("u@example.com"), 403)]:
        assert client.get("/v1/files", headers=headers).status_code == status
        upload = client.post("/v1/files", headers=headers, files=[("files", ("a.md", b"# A\n\nText."))])
        assert upload.status_code == status
        assert client.put("/v1/files/money.md", headers=headers, json={"tags": []}).status_code == status
        assert client.delete("/v1/files/money.md", headers=headers).status_code == status


def test_list_files(env):
    client, _, _ = env
    assert client.get("/v1/files").json() == {
        "total": 1,
        "page": 1,
        "page_size": 50,
        "files": [{"path": "money.md", "size": 65, "tags": []}],
    }


def test_list_files_in_pages(env):
    client, _, settings = env
    for name in ["a.md", "b.md", "c.md"]:
        (settings.kb_root / name).write_text("# A\n\nText.", encoding="utf-8")

    def listed(query):
        body = client.get(f"/v1/files?{query}").json()
        return body["total"], [f["path"] for f in body["files"]]

    assert listed("page_size=3") == (4, ["a.md", "b.md", "c.md"])
    assert listed("page=2&page_size=3") == (4, ["money.md"])
    assert listed("page=3&page_size=3") == (4, [])
    assert client.get("/v1/files?page=0").status_code == 422
    assert client.get("/v1/files?page_size=201").status_code == 422


def test_upload_saves_the_page_and_indexes_it(env):
    client, llm, settings = env

    res = upload(client, ("cards.md", b"# Cards\n\nA card arrives in 3 days.\n"))

    assert res.status_code == 201
    assert res.json() == {"files": ["cards.md"], "sections": 1}
    assert llm.embedded == ["Cards\nA card arrives in 3 days."]
    assert (settings.kb_root / "cards.md").read_text() == "# Cards\n\nA card arrives in 3 days.\n"
    assert [f["path"] for f in client.get("/v1/files").json()["files"]] == ["cards.md", "money.md"]

    ask(client, "When does my card arrive?")
    assert "A card arrives in 3 days." in llm.chats[0][1][0]["content"]


def test_upload_replaces_a_page_with_the_same_name(env, reindex):
    client, llm, _ = env
    reindex()

    res = upload(client, ("money.md", b"# Refunds\n\nA refund takes 2 days.\n"))

    assert res.json()["sections"] == 1
    ask(client, "How long does a refund take?")
    system = llm.chats[0][1][0]["content"]
    assert "A refund takes 2 days." in system
    assert "A refund takes 5 days." not in system


def test_upload_creates_the_knowledge_base_folder(env):
    client, _, settings = env
    (settings.kb_root / "money.md").unlink()
    settings.kb_root.rmdir()
    assert client.get("/v1/files").json()["files"] == []
    assert upload(client, ("a.md", b"# A\n\nText.")).status_code == 201
    assert (settings.kb_root / "a.md").exists()


def test_upload_rejects_invalid_files_and_saves_none(env):
    client, _, settings = env
    folder = settings.kb_root

    assert upload(client, ("ok.md", b"# Ok\n\nText."), ("notes.txt", b"text")).status_code == 400
    assert upload(client, ("ok.md", b"# Ok\n\nText."), ("bad.md", b"\xff\xfe")).status_code == 400
    assert upload(client, (".hidden.md", b"# H\n\nText.")).status_code == 400
    assert upload(client, ("big.md", b"x" * (5 * 1024 * 1024 + 1))).status_code == 413
    assert client.post("/v1/files").status_code == 422

    assert sorted(p.name for p in folder.iterdir()) == ["money.md"]


def test_upload_cannot_write_outside_the_knowledge_base(env):
    client, _, settings = env

    assert upload(client, ("../../escape.md", b"# E\n\nText.")).json()["files"] == ["escape.md"]

    assert (settings.kb_root / "escape.md").exists()
    assert not (settings.kb_root.parent / "escape.md").exists()


def test_delete_removes_the_page_from_disk_and_from_answers(env, reindex):
    client, llm, settings = env
    reindex()

    upload(client, ("cards.md", b"# Cards\n\nA card arrives in 3 days.\n"))
    embedded = len(llm.embedded)

    assert client.delete("/v1/files/money.md").status_code == 204

    assert not (settings.kb_root / "money.md").exists()
    assert [f["path"] for f in client.get("/v1/files").json()["files"]] == ["cards.md"]
    assert len(llm.embedded) == embedded
    ask(client, "How long does a refund take?")
    system = llm.chats[0][1][0]["content"]
    assert "A card arrives in 3 days." in system
    assert "A refund takes 5 days." not in system


def test_delete_handles_pages_in_subfolders(env):
    client, _, settings = env
    guide = settings.kb_root / "guide"
    guide.mkdir()
    (guide / "cards.md").write_text("# Cards\n\nOrder a card.", encoding="utf-8")

    assert client.delete("/v1/files/guide/cards.md").status_code == 204
    assert not (guide / "cards.md").exists()


def test_delete_rejects_unknown_and_outside_paths(env):
    client, _, settings = env
    (settings.kb_root.parent / "secret.md").write_text("# Secret\n\nKeep.", encoding="utf-8")
    (settings.kb_root / "notes.txt").write_text("keep", encoding="utf-8")

    assert client.delete("/v1/files/missing.md").status_code == 404
    assert client.delete("/v1/files/notes.txt").status_code == 404
    assert client.delete("/v1/files/%2E%2E/secret.md").status_code == 404

    assert (settings.kb_root.parent / "secret.md").exists()
    assert (settings.kb_root / "notes.txt").exists()
