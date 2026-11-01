from app.models import Item
from app.routers import items as items_router


def login_headers(client):
    """Register a user, log in, and return headers that authenticate as them."""
    client.post("/auth/register", json={"email": "maya@example.com", "password": "s3cret-pass"})
    response = client.post(
        "/auth/login", json={"email": "maya@example.com", "password": "s3cret-pass"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
