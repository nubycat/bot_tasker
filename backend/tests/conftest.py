import os

import pytest
from httpx import AsyncClient


@pytest.fixture
def api_base_url() -> str:
    # Внутри docker compose сервис backend доступен по имени контейнера
    return os.getenv("API_BASE_URL", "http://backend:8000")


@pytest.fixture
async def client(api_base_url: str) -> AsyncClient:
    async with AsyncClient(base_url=api_base_url) as ac:
        yield ac
