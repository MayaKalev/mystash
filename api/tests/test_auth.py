from httpx import AsyncClient

from app.security import create_access_token


async def register(client: AsyncClient, email: str = "maya@example.com", pw: str = "s3cret-pass"):  # type: ignore[no-untyped-def]
    return await client.post("/auth/register", json={"email": email, "password": pw})


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_register_returns_user_without_password(client: AsyncClient) -> None:
    r = await register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "maya@example.com"
    assert "password" not in body and "password_hash" not in body


async def test_register_lowercases_email_and_rejects_duplicates(client: AsyncClient) -> None:
    assert (await register(client, email="Maya@Example.com")).status_code == 201
    r = await register(client, email="maya@example.com")
    assert r.status_code == 409


async def test_register_validates_input(client: AsyncClient) -> None:
    assert (await register(client, email="not-an-email")).status_code == 422
    assert (await register(client, pw="short")).status_code == 422


async def test_login_and_me(client: AsyncClient) -> None:
    await register(client)
    r = await client.post(
        "/auth/login", json={"email": "MAYA@example.com", "password": "s3cret-pass"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "maya@example.com"


async def test_login_wrong_password_or_unknown_email(client: AsyncClient) -> None:
    await register(client)
    bad_pw = await client.post(
        "/auth/login", json={"email": "maya@example.com", "password": "wrong-pass"}
    )
    unknown = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "s3cret-pass"}
    )
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401
    r = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_me_rejects_token_for_deleted_user(client: AsyncClient) -> None:
    import uuid

    token = create_access_token(uuid.uuid4())
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
