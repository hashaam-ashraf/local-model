from app.services import user_service

ANON = {"Authorization": ""}


def login(client, email, password):
    return client.post("/v1/auth/login", json={"email": email, "password": password}, headers=ANON)


def new_user(client, **fields):
    body = {"email": "ann@example.com", "name": "Ann", "password": "password1", **fields}
    return client.post("/v1/users", json=body)


def test_login_and_me(env):
    client, _, _ = env
    tag = client.post("/v1/tags", json={"name": "billing"}).json()
    assert new_user(client, email="Ann@Example.com", tags=[tag["id"]]).status_code == 201

    assert login(client, "ann@example.com", "wrong-password").status_code == 401
    assert login(client, "nobody@example.com", "password1").status_code == 401
    token = login(client, "ANN@example.com", "password1").json()["token"]

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert (me["email"], me["role"], me["tags"]) == ("ann@example.com", "user", [tag])
    assert "password" not in str(me)


def test_only_admins_manage_users_and_tags(env, as_user):
    client, _, _ = env
    user = as_user("u@example.com")
    user_id = client.get("/v1/auth/me", headers=user).json()["id"]
    for headers, status in [(ANON, 401), (user, 403)]:
        assert client.get("/v1/users", headers=headers).status_code == status
        assert client.post("/v1/users", headers=headers, json={}).status_code == status
        assert client.patch(f"/v1/users/{user_id}", headers=headers, json={"role": "admin"}).status_code == status
        assert client.delete(f"/v1/users/{user_id}", headers=headers).status_code == status
        assert client.get("/v1/tags", headers=headers).status_code == status
        assert client.post("/v1/tags", headers=headers, json={"name": "x"}).status_code == status


def test_create_user_validates(env):
    client, _, _ = env
    assert new_user(client).status_code == 201
    assert new_user(client).status_code == 409
    assert new_user(client, email="b@example.com", password="short").status_code == 422
    assert new_user(client, email="b@example.com", role="owner").status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert new_user(client, email="b@example.com", tags=[unknown]).status_code == 400
    assert [u["email"] for u in client.get("/v1/users").json()["users"]] == ["admin@example.com", "ann@example.com"]


def test_update_and_delete_user(env):
    client, _, _ = env
    tag = client.post("/v1/tags", json={"name": "billing"}).json()
    user = new_user(client).json()

    updated = client.patch(f"/v1/users/{user['id']}", json={"tags": [tag["id"]], "password": "password2"}).json()
    assert (updated["name"], updated["role"], updated["tags"]) == ("Ann", "user", [tag])
    assert login(client, "ann@example.com", "password1").status_code == 401
    token = login(client, "ann@example.com", "password2").json()["token"]

    assert client.delete(f"/v1/users/{user['id']}").status_code == 204
    assert client.delete(f"/v1/users/{user['id']}").status_code == 404
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_cannot_lock_themselves_out(env):
    client, _, _ = env
    me = client.get("/v1/auth/me").json()["id"]
    assert client.patch(f"/v1/users/{me}", json={"role": "user"}).status_code == 400
    assert client.delete(f"/v1/users/{me}").status_code == 400


def test_tags(env):
    client, _, _ = env
    tag = client.post("/v1/tags", json={"name": "billing"})
    assert tag.status_code == 201
    assert client.post("/v1/tags", json={"name": "billing"}).status_code == 409
    assert tag.json()["description"] is None
    assert client.get("/v1/tags").json() == {"total": 1, "page": 1, "page_size": 50, "tags": [tag.json()]}

    user = new_user(client, tags=[tag.json()["id"]]).json()
    assert client.delete(f"/v1/tags/{tag.json()['id']}").status_code == 204
    assert client.delete(f"/v1/tags/{tag.json()['id']}").status_code == 404
    assert client.patch(f"/v1/users/{user['id']}", json={}).json()["tags"] == []


def test_login_is_refused_without_a_secret_key(env):
    client, _, settings = env
    new_user(client)
    settings.secret_key = ""
    assert login(client, "ann@example.com", "password1").status_code == 401
    assert client.get("/v1/models").status_code == 401


def test_users_and_tags_are_listed_in_pages(env):
    client, _, _ = env
    for name in ["b", "a", "c"]:
        tag = client.post("/v1/tags", json={"name": name, "description": f"About {name}"}).json()
        assert tag["description"] == f"About {name}"
        new_user(client, email=f"{name}@example.com")

    def listed(path, key, field, query):
        body = client.get(f"/v1/{path}?{query}").json()
        return body["total"], [item[field] for item in body[key]]

    assert listed("tags", "tags", "name", "page_size=2") == (3, ["a", "b"])
    assert listed("tags", "tags", "name", "page=2&page_size=2") == (3, ["c"])
    assert listed("users", "users", "email", "page=2&page_size=3") == (4, ["c@example.com"])
    assert listed("users", "users", "email", "page=3&page_size=3") == (4, [])
    for path in ["tags", "users"]:
        assert client.get(f"/v1/{path}?page=0").status_code == 422
        assert client.get(f"/v1/{path}?page_size=201").status_code == 422


def test_seed_admin_creates_the_admin_once(env):
    client, _, _ = env
    with client.app.state.sessions() as db:
        assert user_service.seed_admin(db, "Root@Example.com", "password1") is True
        assert user_service.seed_admin(db, "root@example.com", "password2") is False

    assert login(client, "root@example.com", "password2").status_code == 401
    token = login(client, "root@example.com", "password1").json()["token"]
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["role"] == "admin"
