import pytest


async def _register_and_token(client, email="sub@example.com"):
    r = await client.post("/users/register", json={"email": email, "password": "pass123"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_subscription(user_client):
    token = await _register_and_token(user_client, "sub1@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await user_client.post("/subscriptions", json={
        "name": "СПб 2-комнатные",
        "channel": "telegram",
        "filter_city": "Санкт-Петербург",
        "filter_rooms_min": 2,
        "filter_price_max": 60000,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "СПб 2-комнатные"
    assert data["filter_city"] == "Санкт-Петербург"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_toggle_subscription(user_client):
    token = await _register_and_token(user_client, "sub2@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = await user_client.post("/subscriptions", json={"name": "test", "channel": "telegram"}, headers=headers)
    sub_id = r.json()["id"]

    resp = await user_client.patch(f"/subscriptions/{sub_id}", json={"is_active": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_subscription(user_client):
    token = await _register_and_token(user_client, "sub3@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = await user_client.post("/subscriptions", json={"name": "del", "channel": "telegram"}, headers=headers)
    sub_id = r.json()["id"]

    resp = await user_client.delete(f"/subscriptions/{sub_id}", headers=headers)
    assert resp.status_code == 204

    resp = await user_client.get("/subscriptions", headers=headers)
    assert all(s["id"] != sub_id for s in resp.json())
