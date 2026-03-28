import pytest


@pytest.mark.asyncio
async def test_register_success(user_client):
    resp = await user_client.post("/users/register", json={
        "email": "test@example.com",
        "password": "secret123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(user_client):
    payload = {"email": "dup@example.com", "password": "secret123"}
    await user_client.post("/users/register", json=payload)
    resp = await user_client.post("/users/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(user_client):
    payload = {"email": "login@example.com", "password": "secret123"}
    await user_client.post("/users/register", json=payload)
    resp = await user_client.post("/users/login", json=payload)
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(user_client):
    await user_client.post("/users/register", json={"email": "pw@example.com", "password": "correct"})
    resp = await user_client.post("/users/login", json={"email": "pw@example.com", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(user_client):
    resp = await user_client.get("/users/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_returns_profile(user_client):
    reg = await user_client.post("/users/register", json={"email": "me@example.com", "password": "pass123"})
    token = reg.json()["access_token"]
    resp = await user_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"
