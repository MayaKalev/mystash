from app.models import Item, ItemTag, Tag, User
from app.routers import items as items_router


def login_headers(client, email="maya@example.com"):
    """Register a user, log in, and return headers that authenticate as them."""
    client.post("/auth/register", json={"email": email, "password": "s3cret-pass"})
    response = client.post("/auth/login", json={"email": email, "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def user_id(db, email="maya@example.com"):
    return db.query(User).filter_by(email=email).one().id


def add_item(db, owner_id, url="https://example.com/post"):
    item = Item(user_id=owner_id, url=url, status="pending")
    db.add(item)
    db.commit()
    return item


def test_create_item_saves_pending_item_and_queues_job(client, db, monkeypatch):
    queued = []
    monkeypatch.setattr(items_router.queue, "enqueue", lambda func, *args: queued.append(args))

    response = client.post(
        "/items", json={"url": "https://example.com/post"}, headers=login_headers(client)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["url"] == "https://example.com/post"
    assert body["status"] == "pending"
    assert queued == [(body["id"],)]
    assert db.get(Item, body["id"]).status == "pending"


def test_create_item_needs_login(client):
    response = client.post("/items", json={"url": "https://example.com"})
    assert response.status_code == 401


def test_create_item_rejects_bad_url(client):
    response = client.post("/items", json={"url": "not a url"}, headers=login_headers(client))
    assert response.status_code == 422


def test_list_items_newest_first(client, db):
    headers = login_headers(client)
    first = add_item(db, user_id(db), "https://example.com/first")
    second = add_item(db, user_id(db), "https://example.com/second")

    response = client.get("/items", headers=headers)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [second.id, first.id]


def test_list_items_only_shows_own_items(client, db):
    headers = login_headers(client)
    login_headers(client, email="other@example.com")
    add_item(db, user_id(db, "other@example.com"))

    assert client.get("/items", headers=headers).json() == []


def test_list_items_needs_login(client):
    assert client.get("/items").status_code == 401


def test_get_item_includes_ai_results(client, db):
    headers = login_headers(client)
    item = add_item(db, user_id(db))
    item.summary = "A summary"
    item.content_type = "article"
    item.extracted_text = "The full page text"
    tag = Tag(user_id=item.user_id, name="python")
    db.add(tag)
    db.commit()
    db.add(ItemTag(item_id=item.id, tag_id=tag.id, source="ai"))
    db.commit()

    response = client.get(f"/items/{item.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "A summary"
    assert body["content_type"] == "article"
    assert body["tags"] == [{"name": "python"}]
    assert "extracted_text" not in body


def test_get_item_not_found(client):
    assert client.get("/items/12345", headers=login_headers(client)).status_code == 404


def test_get_item_of_another_user_is_not_found(client, db):
    headers = login_headers(client)
    login_headers(client, email="other@example.com")
    item = add_item(db, user_id(db, "other@example.com"))

    assert client.get(f"/items/{item.id}", headers=headers).status_code == 404


def test_get_item_needs_login(client):
    assert client.get("/items/1").status_code == 401
