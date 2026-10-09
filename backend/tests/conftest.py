import asyncio
import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "knowflow-test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/15"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes"
os.environ["LLM_DEFAULT_PROVIDER"] = "ollama"
os.environ["OPENAI_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["MOONSHOT_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import engine
from app.models import Base
import app.api.v1.contents as contents_routes


async def _reset_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def clean_database():
    asyncio.run(_reset_database())
    yield


@pytest.fixture
def client(monkeypatch):
    async def no_background_processing(*args, **kwargs):
        return None

    monkeypatch.setattr(
        contents_routes, "process_content_with_ai", no_background_processing
    )
    with TestClient(app) as test_client:
        yield test_client
