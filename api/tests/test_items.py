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


def add_tag(db, item, name, source="ai"):
    tag = db.query(Tag).filter_by(user_id=item.user_id, name=name).one_or_none()
    if tag is None:
        tag = Tag(user_id=item.user_id, name=name)
        db.add(tag)
        db.commit()
    db.add(ItemTag(item_id=item.id, tag_id=tag.id, source=source))
    db.commit()


def done_item(db, owner_id, url="https://example.com/post", content_type="article"):
    item = add_item(db, owner_id, url)
    item.status = "done"
    item.content_type = content_type
    db.commit()
    return item


def ids(response):
    return [item["id"] for item in response.json()]


def test_list_items_filters_by_status_and_type(client, db):
    headers = login_headers(client)
    article = done_item(db, user_id(db), content_type="article")
    video = done_item(db, user_id(db), content_type="video")
    pending = add_item(db, user_id(db))

    assert ids(client.get("/items?content_type=video", headers=headers)) == [video.id]
    assert ids(client.get("/items?status=pending", headers=headers)) == [pending.id]
    assert ids(client.get("/items?status=done&content_type=article", headers=headers)) == [
        article.id
    ]


def test_list_items_filters_by_tag(client, db):
    headers = login_headers(client)
    tagged = done_item(db, user_id(db))
    done_item(db, user_id(db))
    add_tag(db, tagged, "python")

    assert ids(client.get("/items?tag=python", headers=headers)) == [tagged.id]


def test_tag_filter_ignores_other_users_tags(client, db):
    headers = login_headers(client)
    login_headers(client, email="other@example.com")
    add_tag(db, done_item(db, user_id(db, "other@example.com")), "python")

    assert client.get("/items?tag=python", headers=headers).json() == []


def test_update_tags_adds_and_removes(client, db):
    headers = login_headers(client)
    item = done_item(db, user_id(db))
    add_tag(db, item, "python")
    add_tag(db, item, "web")

    response = client.put(
        f"/items/{item.id}/tags", json={"tags": ["Python", "My-Notes"]}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["tags"] == [{"name": "my notes"}, {"name": "python"}]
    sources = {
        tag.name: link.source
        for link, tag in db.query(ItemTag, Tag).join(Tag).filter(ItemTag.item_id == item.id)
    }
    # The kept AI tag stays "ai"; the new one is "user".
    assert sources == {"python": "ai", "my notes": "user"}


def test_update_tags_reuses_existing_tag(client, db):
    headers = login_headers(client)
    first = done_item(db, user_id(db))
    second = done_item(db, user_id(db))
    add_tag(db, first, "python")

    client.put(f"/items/{second.id}/tags", json={"tags": ["python"]}, headers=headers)

    assert db.query(Tag).filter_by(name="python").count() == 1


def test_update_tags_waits_for_processing(client, db):
    headers = login_headers(client)
    item = add_item(db, user_id(db))

    response = client.put(f"/items/{item.id}/tags", json={"tags": ["python"]}, headers=headers)

    assert response.status_code == 409


def test_update_tags_of_another_user_is_not_found(client, db):
    headers = login_headers(client)
    login_headers(client, email="other@example.com")
    item = done_item(db, user_id(db, "other@example.com"))

    response = client.put(f"/items/{item.id}/tags", json={"tags": ["x"]}, headers=headers)

    assert response.status_code == 404


def test_delete_item(client, db):
    headers = login_headers(client)
    item = done_item(db, user_id(db))
    add_tag(db, item, "python")
    item_id = item.id

    response = client.delete(f"/items/{item_id}", headers=headers)

    assert response.status_code == 204
    db.expire_all()
    assert db.get(Item, item_id) is None
    assert db.query(ItemTag).count() == 0


def test_delete_item_of_another_user_is_not_found(client, db):
    headers = login_headers(client)
    login_headers(client, email="other@example.com")
    item = add_item(db, user_id(db, "other@example.com"))

    assert client.delete(f"/items/{item.id}", headers=headers).status_code == 404
    db.expire_all()
    assert db.get(Item, item.id) is not None


def test_list_tags_only_shows_own_tags_in_use(client, db):
    headers = login_headers(client)
    login_headers(client, email="other@example.com")
    item = done_item(db, user_id(db))
    add_tag(db, item, "web")
    add_tag(db, item, "python")
    add_tag(db, done_item(db, user_id(db, "other@example.com")), "secret")
    db.add(Tag(user_id=user_id(db), name="unused"))
    db.commit()

    response = client.get("/tags", headers=headers)

    assert response.json() == [{"name": "python"}, {"name": "web"}]


def test_list_tags_needs_login(client):
    assert client.get("/tags").status_code == 401


def test_cors_allows_the_website(client):
    response = client.options(
        "/items",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
