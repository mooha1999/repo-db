"""Test fixtures for RepoGen tests."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.test_models.models import Base

# Path to the test models
TEST_MODELS_DIR = Path(__file__).parent / "test_models"


@pytest.fixture(scope="session")
def test_models_path():
    """Path to the test models directory."""
    return TEST_MODELS_DIR


@pytest.fixture(scope="session")
def test_models_file():
    """Path to a single test models file."""
    return TEST_MODELS_DIR / "models.py"


@pytest.fixture(scope="session")
def generated_package(tmp_path_factory):
    """Run the repogen CLI to generate code and make it importable.

    This fixture runs `repogen generate` as a subprocess (the real CLI entry
    point), then adds the output to sys.path so every generated module can be
    imported normally.  The fixture is session-scoped so generation only
    happens once.
    """
    output = tmp_path_factory.mktemp("cli_generated")
    models_path = str(TEST_MODELS_DIR / "models.py")

    result = subprocess.run(
        [
            sys.executable, "-m", "repogen", "generate",
            "--models", models_path,
            "--output", str(output),
            "--verbose",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"repogen generate failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Make the generated package importable
    if str(output.parent) not in sys.path:
        sys.path.insert(0, str(output.parent))

    # The generated repos do `from models import User` etc, so test_models
    # dir must also be importable.
    if str(TEST_MODELS_DIR) not in sys.path:
        sys.path.insert(0, str(TEST_MODELS_DIR))

    return output


def _import_generated(generated_package, module_suffix: str):
    """Import a generated module by suffix, e.g. 'user_repository'."""
    mod_name = f"{generated_package.name}.{module_suffix}"
    # Always reload to avoid stale cache across test files
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    return importlib.import_module(mod_name)


@pytest.fixture(scope="session")
def gen_import(generated_package):
    """Return a helper function to import generated modules."""
    def _import(module_suffix: str):
        return _import_generated(generated_package, module_suffix)
    return _import


@pytest.fixture
async def async_engine():
    """Create an async SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    """Create an async session with all tables created."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        async with session.begin():
            yield session


@pytest.fixture
def output_dir(tmp_path):
    """Temporary output directory for generated files."""
    out = tmp_path / "generated"
    out.mkdir()
    return out
