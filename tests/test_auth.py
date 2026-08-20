import pytest

pytestmark = pytest.mark.asyncio


async def test_register_creates_account(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new.user@example.com",
            "password": "Str0ngPassw0rd!",
            "full_name": "New User",
            "country_code": "IN",
        },
    )
    body = response.json()

    assert response.status_code == 201
    assert body["success"] is True
    assert body["data"]["email"] == "new.user@example.com"
    assert body["data"]["role"] == "student"


async def test_register_rejects_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "Str0ngPassw0rd!",
        "full_name": "Dup User",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["success"] is False


async def test_register_rejects_short_password(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "Weak Pw"},
    )
    assert response.status_code == 422


async def test_login_success_returns_tokens(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "Str0ngPassw0rd!", "full_name": "Login User"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "Str0ngPassw0rd!"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["data"]["access_token"]
    assert body["data"]["refresh_token"]
    assert body["data"]["token_type"] == "bearer"


async def test_login_rejects_wrong_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "Str0ngPassw0rd!", "full_name": "User"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPassword!"}
    )
    assert response.status_code == 401


async def test_login_rejects_unknown_email(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Str0ngPassw0rd!"}
    )
    assert response.status_code == 401


async def test_me_requires_authentication(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client, registered_user):
    headers, _ = await registered_user()
    response = await client.get("/api/v1/auth/me", headers=headers)
    body = response.json()

    assert response.status_code == 200
    assert body["data"]["email"] == "student@example.com"


async def test_me_rejects_invalid_token(client):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_token_and_invalidates_old_one(client, registered_user):
    _, tokens = await registered_user()

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()["data"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The old (now-rotated) refresh token must be rejected on reuse.
    reuse_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse_response.status_code == 401


async def test_logout_revokes_refresh_token(client, registered_user):
    _, tokens = await registered_user()

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_response.status_code == 200

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 401
