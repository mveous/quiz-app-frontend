import pytest

pytestmark = pytest.mark.asyncio


async def test_non_admin_gets_403_on_admin_routes(client, registered_user):
    headers, _ = await registered_user()
    response = await client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 403


async def test_unauthenticated_gets_401_on_admin_routes(client):
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 401


async def test_admin_can_list_users(client, admin_user, registered_user):
    headers, _ = await admin_user()
    await registered_user("student1@example.com")
    await registered_user("student2@example.com")

    response = await client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


async def test_admin_can_search_users(client, admin_user):
    headers, _ = await admin_user()
    response = await client.get(
        "/api/v1/admin/users", params={"search": "admin@example.com"}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["email"] == "admin@example.com"


async def test_admin_can_get_single_user(client, admin_user, registered_user):
    admin_headers, _ = await admin_user()
    _, student_tokens = await registered_user("student@example.com")

    list_response = await client.get(
        "/api/v1/admin/users", params={"search": "student@example.com"}, headers=admin_headers
    )
    student_id = list_response.json()["data"]["items"][0]["id"]

    response = await client.get(f"/api/v1/admin/users/{student_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "student@example.com"


async def test_get_unknown_user_returns_404(client, admin_user):
    headers, _ = await admin_user()
    response = await client.get(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert response.status_code == 404


async def test_admin_can_change_user_role(client, admin_user, registered_user):
    admin_headers, _ = await admin_user()
    await registered_user("student@example.com")

    list_response = await client.get(
        "/api/v1/admin/users", params={"search": "student@example.com"}, headers=admin_headers
    )
    student_id = list_response.json()["data"]["items"][0]["id"]

    response = await client.patch(
        f"/api/v1/admin/users/{student_id}/role", json={"role": "admin"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"


async def test_admin_can_deactivate_another_user(client, admin_user, registered_user):
    admin_headers, _ = await admin_user()
    await registered_user("student@example.com")

    list_response = await client.get(
        "/api/v1/admin/users", params={"search": "student@example.com"}, headers=admin_headers
    )
    student_id = list_response.json()["data"]["items"][0]["id"]

    response = await client.patch(
        f"/api/v1/admin/users/{student_id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


async def test_admin_cannot_deactivate_self(client, admin_user):
    headers, tokens = await admin_user()
    me_response = await client.get("/api/v1/auth/me", headers=headers)
    admin_id = me_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/admin/users/{admin_id}/status", json={"is_active": False}, headers=headers
    )
    assert response.status_code == 422


async def test_admin_cannot_remove_own_admin_role(client, admin_user):
    headers, _ = await admin_user()
    me_response = await client.get("/api/v1/auth/me", headers=headers)
    admin_id = me_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/admin/users/{admin_id}/role", json={"role": "student"}, headers=headers
    )
    assert response.status_code == 422


async def test_system_health_returns_status(client, admin_user):
    headers, _ = await admin_user()
    response = await client.get("/api/v1/admin/system-health", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["database"] is True
    assert "redis" in data
    assert data["ai_provider"] == "mock"
