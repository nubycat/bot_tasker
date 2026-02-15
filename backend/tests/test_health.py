import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    # сейчас {"status":"ok"} — проверяем именно это
    assert data.get("status") == "ok"
