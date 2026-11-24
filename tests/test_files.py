from fastapi.testclient import TestClient

from app.main import create_app

ADMIN = {"Authorization": "Bearer secret"}


def upload(client, slug, *files):
    return client.post(
        f"/v1/{slug}/files", headers=ADMIN, files=[("files", (name, content)) for name, content in files]
    )


def ask(client, text):
    return client.post("/v1/demo/chat", json={"messages": [{"role": "user", "content": text}]})


def test_files_require_admin_token(env):
    client, _, _ = env
    assert client.get("/v1/demo/files").status_code == 401
    assert client.post("/v1/demo/files", files=[("files", ("a.md", b"# A\n\nText."))]).status_code == 401
    assert client.delete("/v1/demo/files/money.md").status_code == 401


def test_list_files(env):
    client, _, _ = env
    assert client.get("/v1/demo/files", headers=ADMIN).json() == {
        "total": 1,
        "page": 1,
        "page_size": 50,
        "files": [{"path": "money.md", "size": 65}],
    }


def test_list_files_in_pages(env):
    client, _, settings = env
    for name in ["a.md", "b.md", "c.md"]:
        (settings.kb_root / "demo-kb" / name).write_text("# A\n\nText.", encoding="utf-8")

    def listed(query):
        body = client.get(f"/v1/demo/files?{query}", headers=ADMIN).json()
        return body["total"], [f["path"] for f in body["files"]]

    assert listed("page_size=3") == (4, ["a.md", "b.md", "c.md"])
    assert listed("page=2&page_size=3") == (4, ["money.md"])
    assert listed("page=3&page_size=3") == (4, [])
    assert client.get("/v1/demo/files?page=0", headers=ADMIN).status_code == 422
    assert client.get("/v1/demo/files?page_size=201", headers=ADMIN).status_code == 422


def test_upload_saves_the_page_and_indexes_it(env):
    client, llm, settings = env

    res = upload(client, "demo", ("cards.md", b"# Cards\n\nA card arrives in 3 days.\n"))

    assert res.status_code == 201
    assert res.json() == {"project": "demo", "files": ["cards.md"], "sections": 1}
    assert llm.embedded == ["Cards\nA card arrives in 3 days."]
    assert (settings.kb_root / "demo-kb" / "cards.md").read_text() == "# Cards\n\nA card arrives in 3 days.\n"
    assert [f["path"] for f in client.get("/v1/demo/files", headers=ADMIN).json()["files"]] == ["cards.md", "money.md"]

    ask(client, "When does my card arrive?")
    assert "A card arrives in 3 days." in llm.chats[0][1][0]["content"]


def test_upload_replaces_a_page_with_the_same_name(env):
    client, llm, _ = env
    client.post("/v1/demo/index", headers=ADMIN)

    res = upload(client, "demo", ("money.md", b"# Refunds\n\nA refund takes 2 days.\n"))

    assert res.json()["sections"] == 1
    ask(client, "How long does a refund take?")
    system = llm.chats[0][1][0]["content"]
    assert "A refund takes 2 days." in system
    assert "A refund takes 5 days." not in system


def test_upload_creates_the_knowledge_base_folder(env):
    client, _, settings = env
    (settings.projects_dir / "fresh.toml").write_text(
        'name = "Fresh"\nsystem_prompt = "Hi."\nkb_path = "fresh-kb"\n', encoding="utf-8"
    )
    client = TestClient(create_app(settings, client.app.state.llm, client.app.state.store))
    assert client.get("/v1/fresh/files", headers=ADMIN).json()["files"] == []
    assert upload(client, "fresh", ("a.md", b"# A\n\nText.")).status_code == 201
    assert (settings.kb_root / "fresh-kb" / "a.md").exists()


def test_upload_rejects_invalid_files_and_saves_none(env):
    client, _, settings = env
    folder = settings.kb_root / "demo-kb"

    assert upload(client, "demo", ("ok.md", b"# Ok\n\nText."), ("notes.txt", b"text")).status_code == 400
    assert upload(client, "demo", ("ok.md", b"# Ok\n\nText."), ("bad.md", b"\xff\xfe")).status_code == 400
    assert upload(client, "demo", (".hidden.md", b"# H\n\nText.")).status_code == 400
    assert upload(client, "demo", ("big.md", b"x" * (5 * 1024 * 1024 + 1))).status_code == 413
    assert client.post("/v1/demo/files", headers=ADMIN).status_code == 422

    assert sorted(p.name for p in folder.iterdir()) == ["money.md"]


def test_upload_cannot_write_outside_the_knowledge_base(env):
    client, _, settings = env

    assert upload(client, "demo", ("../../escape.md", b"# E\n\nText.")).json()["files"] == ["escape.md"]

    assert (settings.kb_root / "demo-kb" / "escape.md").exists()
    assert not (settings.kb_root.parent / "escape.md").exists()


def test_delete_removes_the_page_from_disk_and_from_answers(env):
    client, llm, settings = env
    client.post("/v1/demo/index", headers=ADMIN)

    upload(client, "demo", ("cards.md", b"# Cards\n\nA card arrives in 3 days.\n"))
    embedded = len(llm.embedded)

    assert client.delete("/v1/demo/files/money.md", headers=ADMIN).status_code == 204

    assert not (settings.kb_root / "demo-kb" / "money.md").exists()
    assert [f["path"] for f in client.get("/v1/demo/files", headers=ADMIN).json()["files"]] == ["cards.md"]
    assert len(llm.embedded) == embedded
    ask(client, "How long does a refund take?")
    system = llm.chats[0][1][0]["content"]
    assert "A card arrives in 3 days." in system
    assert "A refund takes 5 days." not in system


def test_delete_handles_pages_in_subfolders(env):
    client, _, settings = env
    guide = settings.kb_root / "demo-kb" / "guide"
    guide.mkdir()
    (guide / "cards.md").write_text("# Cards\n\nOrder a card.", encoding="utf-8")

    assert client.delete("/v1/demo/files/guide/cards.md", headers=ADMIN).status_code == 204
    assert not (guide / "cards.md").exists()


def test_delete_rejects_unknown_and_outside_paths(env):
    client, _, settings = env
    (settings.kb_root / "secret.md").write_text("# Secret\n\nKeep.", encoding="utf-8")
    (settings.kb_root / "demo-kb" / "notes.txt").write_text("keep", encoding="utf-8")

    assert client.delete("/v1/demo/files/missing.md", headers=ADMIN).status_code == 404
    assert client.delete("/v1/demo/files/notes.txt", headers=ADMIN).status_code == 404
    assert client.delete("/v1/demo/files/%2E%2E/secret.md", headers=ADMIN).status_code == 404

    assert (settings.kb_root / "secret.md").exists()
    assert (settings.kb_root / "demo-kb" / "notes.txt").exists()


def test_project_without_kb_has_no_files(env):
    client, _, _ = env
    assert client.get("/v1/plain/files", headers=ADMIN).status_code == 400
    assert upload(client, "plain", ("a.md", b"# A\n\nText.")).status_code == 400
    assert client.delete("/v1/plain/files/a.md", headers=ADMIN).status_code == 400
