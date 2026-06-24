"""Tests del ciclo de autenticacion: registro, login, refresh y logout (revocacion)."""


def test_register_and_login(client):
    r = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "secret123", "full_name": "Ana"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "client"

    r = client.post("/auth/login", data={"username": "ana@example.com", "password": "secret123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body and "refresh_token" in body


def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "secret123", "full_name": "Dup"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "secret123", "full_name": "Bob"},
    )
    r = client.post("/auth/login", data={"username": "bob@example.com", "password": "WRONG"})
    assert r.status_code == 401


def test_protected_endpoint_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_refresh_returns_new_access_token(client):
    client.post(
        "/auth/register",
        json={"email": "cy@example.com", "password": "secret123", "full_name": "Cy"},
    )
    tokens = client.post(
        "/auth/login", data={"username": "cy@example.com", "password": "secret123"}
    ).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_logout_revokes_refresh_token(client):
    """Tras logout, el refresh token deja de servir (la sesion se invalida)."""
    client.post(
        "/auth/register",
        json={"email": "leo@example.com", "password": "secret123", "full_name": "Leo"},
    )
    tokens = client.post(
        "/auth/login", data={"username": "leo@example.com", "password": "secret123"}
    ).json()
    rt = tokens["refresh_token"]

    assert client.post("/auth/refresh", json={"refresh_token": rt}).status_code == 200
    assert client.post("/auth/logout", json={"refresh_token": rt}).status_code == 204
    # Ya revocado -> 401
    assert client.post("/auth/refresh", json={"refresh_token": rt}).status_code == 401
