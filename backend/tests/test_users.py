# backend/tests/test_users.py

import pytest


import pytest


@pytest.mark.asyncio
async def test_create_user(client):
    r = await client.post(
        "/users/upsert",
        json={
            "telegram_id": 123,
            "username": "rustam",
            "first_name": "Rustam",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["telegram_id"] == 123
    assert data["username"] == "rustam"
