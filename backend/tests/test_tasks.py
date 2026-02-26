# backend/tests/test_tasks.py

import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw, expected_suffix",
    [
        ("18", "18:00"),
        ("830", "08:30"),
        ("2118", "21:18"),
        ("8:3", "08:03"),
        ("18:30", "18:30"),
    ],
)
async def test_create_from_bot_remind_at_normalizes(client, raw, expected_suffix):
    resp = await client.post(
        "/tasks",
        json={
            "telegram_id": 100,
            "title": "t",
            "description": None,
            "remind_at": raw,
            "username": "u",
            "first_name": "f",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    # due_at хранится datetime, но нам важно что HH:MM выставились корректно
    # поэтому проверим строковое представление конца
    assert data["due_at"].endswith(f"{expected_suffix}:00") or data["due_at"].endswith(
        f"{expected_suffix}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    ["", "aa", "18-30", "1::2", "2360", "23:60", "24", "24:00", "-1", "99", "9999"],
)
async def test_create_from_bot_invalid_remind_at_422(client, bad):
    resp = await client.post(
        "/tasks",
        json={
            "telegram_id": 101,
            "title": "t",
            "description": None,
            "remind_at": bad,
            "username": None,
            "first_name": None,
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_from_bot_empty_title_422(client):
    resp = await client.post(
        "/tasks",
        json={
            "telegram_id": 102,
            "title": "",
            "description": None,
            "remind_at": "18",
            "username": "u",
            "first_name": "f",
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_personal_user_not_found_404(client):
    resp = await client.post(
        "/tasks/personal?telegram_id=9999",
        json={
            "title": "x",
            "description": None,
            "due_at": None,
        },
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_personal_task_access_denied_as_not_found(client):
    # user A
    await client.post(
        "/users/upsert", json={"telegram_id": 201, "username": "a", "first_name": "a"}
    )
    # user B
    await client.post(
        "/users/upsert", json={"telegram_id": 202, "username": "b", "first_name": "b"}
    )

    # create personal task for A
    r = await client.post(
        "/tasks/personal?telegram_id=201",
        json={
            "title": "secret",
            "description": None,
            "due_at": None,
        },
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["id"]

    # B tries to fetch it
    r2 = await client.get(f"/tasks/personal/{task_id}?telegram_id=202")
    assert r2.status_code == 404, r2.text


@pytest.mark.asyncio
async def test_team_today_without_active_team_400(client):
    await client.post(
        "/users/upsert", json={"telegram_id": 301, "username": "u", "first_name": "u"}
    )
    resp = await client.get("/tasks/team/today?telegram_id=301")
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_context_today_returns_empty_for_unknown_user(client):
    r = await client.get("/tasks/today?telegram_id=123456")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["open"] == []
    assert data["done"] == []
