def register(client, email="maya@example.com", password="s3cret-pass"):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email="maya@example.com", password="s3cret-pass"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["email"] == "maya@example.com"
    assert "password_hash" not in response.json()


def test_register_same_email_twice(client):
    register(client, email="Maya@Example.com")
    response = register(client, email="maya@example.com")
    assert response.status_code == 409


def test_register_bad_input(client):
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="short").status_code == 422


def test_login_and_get_me(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    token = response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "maya@example.com"


def test_login_wrong_password(client):
    register(client)
    assert login(client, password="wrong-pass").status_code == 401


def test_login_unknown_email(client):
    assert login(client, email="nobody@example.com").status_code == 401


def test_me_without_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_bad_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
