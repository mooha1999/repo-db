"""Test fixtures for RepoGen tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)

# Path to the test models
TEST_MODELS_DIR = Path(__file__).parent / "test_models"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_models_path():
    """Path to the test models directory."""
    return TEST_MODELS_DIR


@pytest.fixture
def test_models_file():
    """Path to a single test models file."""
    return TEST_MODELS_DIR / "models.py"


@pytest.fixture
async def async_engine():
    """Create an async SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine: AsyncEngine):
    """Create an async session for testing."""
    from tests.test_models.models import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def output_dir(tmp_path: Path):
    """Temporary output directory for generated files."""
    out = tmp_path / "generated"
    out.mkdir()
    return out
