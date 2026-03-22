"""End-to-end integration tests: generate repos from models, then use them against a real async DB."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from repogen.generators.dto_generator import generate_dtos
from repogen.generators.filter_generator import generate_filters
from repogen.generators.internals_generator import generate_internals
from repogen.generators.loading_generator import generate_load_options
from repogen.generators.repo_generator import generate_repository
from repogen.introspection.engine import discover_models
from tests.test_models.models import Base


@pytest.fixture(scope="module")
def generated_dir(tmp_path_factory):
    """Generate all code to a temp dir and make it importable."""
    output = tmp_path_factory.mktemp("generated")
    models_path = Path(__file__).parent / "test_models" / "models.py"
    model_irs = discover_models(str(models_path))

    # Create __init__.py for the package
    (output / "__init__.py").write_text("")

    generate_internals(output)
    for m in model_irs:
        generate_dtos(m, output)
        generate_filters(m, output)
        generate_load_options(m, model_irs, output)
        generate_repository(m, output, internals_path=output.name, config={
            "generate_unique_lookups": True,
            "generate_hard_delete": True,
            "generate_restore": True,
        })

    # Make importable
    parent = str(output.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # The generated repo files import `from models import ...`
    # so ensure the test_models dir is on sys.path
    test_models_dir = str(Path(__file__).parent / "test_models")
    if test_models_dir not in sys.path:
        sys.path.insert(0, test_models_dir)

    return output


@pytest.fixture
async def session():
    """Fresh in-memory SQLite session for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess
    await engine.dispose()


def _import(generated_dir, module_name):
    """Import a generated module by name."""
    full = f"{generated_dir.name}.{module_name}"
    # Invalidate caches in case of repeated imports
    if full in sys.modules:
        return sys.modules[full]
    return importlib.import_module(full)


# ─── User CRUD (soft-deletable) ──────────────────────────────────────────


async def test_create_and_get_user(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Alice", email="alice@test.com"))
    assert user.id is not None
    assert user.name == "Alice"

    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.email == "alice@test.com"


async def test_create_many_users(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    users = await repo.create_many([
        dto_mod.UserCreate(name="Bob", email="bob@test.com"),
        dto_mod.UserCreate(name="Carol", email="carol@test.com"),
    ])
    assert len(users) == 2
    assert {u.name for u in users} == {"Bob", "Carol"}


async def test_user_update(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Dave", email="dave@test.com"))

    updated = await repo.update(dto_mod.UserUpdate(id=user.id, name="David"))
    assert updated is not None
    assert updated.name == "David"
    assert updated.email == "dave@test.com"  # unchanged


async def test_user_soft_delete(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Eve", email="eve@test.com"))

    result = await repo.delete(user.id)
    assert result is True

    # Not found by default (soft-deleted)
    assert await repo.get_by_id(user.id) is None

    # Found with include_deleted
    found = await repo.get_by_id(user.id, include_deleted=True)
    assert found is not None
    assert found.deleted_at is not None


async def test_user_restore(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Frank", email="frank@test.com"))
    await repo.delete(user.id)

    restored = await repo.restore(user.id)
    assert restored is not None
    assert restored.deleted_at is None

    # Now findable without include_deleted
    found = await repo.get_by_id(user.id)
    assert found is not None


async def test_user_hard_delete(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Grace", email="grace@test.com"))

    result = await repo.hard_delete(user.id)
    assert result is True

    # Permanently gone — not even with include_deleted
    assert await repo.get_by_id(user.id, include_deleted=True) is None


async def test_user_get_by_email(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Heidi", email="heidi@test.com"))

    found = await repo.get_by_email("heidi@test.com")
    assert found is not None
    assert found.name == "Heidi"

    assert await repo.get_by_email("nonexistent@test.com") is None


async def test_user_count_and_exists(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")
    filter_mod = _import(generated_dir, "user_filters")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Ivan", email="ivan@test.com"))
    await repo.create(dto_mod.UserCreate(name="Judy", email="judy@test.com"))

    assert await repo.count() == 2

    name_filter = filter_mod.UserFilter(
        name=filter_mod.StringFilter(eq="Ivan")
    )
    assert await repo.exists(filters=name_filter) is True

    missing_filter = filter_mod.UserFilter(
        name=filter_mod.StringFilter(eq="Nonexistent")
    )
    assert await repo.exists(filters=missing_filter) is False


async def test_user_filter_by_name(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")
    filter_mod = _import(generated_dir, "user_filters")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Karl", email="karl@test.com"))
    await repo.create(dto_mod.UserCreate(name="Liam", email="liam@test.com"))
    await repo.create(dto_mod.UserCreate(name="Karl2", email="karl2@test.com"))

    results = await repo.get_many(
        filters=filter_mod.UserFilter(
            name=filter_mod.StringFilter(like="Karl%")
        )
    )
    assert len(results) == 2
    assert all("Karl" in r.name for r in results)


async def test_user_get_many_order_and_limit(generated_dir, session):
    repo_mod = _import(generated_dir, "user_repository")
    dto_mod = _import(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Zara", email="zara@test.com"))
    await repo.create(dto_mod.UserCreate(name="Amy", email="amy@test.com"))
    await repo.create(dto_mod.UserCreate(name="Mia", email="mia@test.com"))

    results = await repo.get_many(order_by=["name"], limit=2)
    assert len(results) == 2
    assert results[0].name == "Amy"
    assert results[1].name == "Mia"


# ─── Policy CRUD (non-soft-deletable) ────────────────────────────────────


async def test_policy_create_and_hard_delete(generated_dir, session):
    # Need a user first (FK)
    user_repo_mod = _import(generated_dir, "user_repository")
    user_dto_mod = _import(generated_dir, "user_dtos")
    repo_mod = _import(generated_dir, "policy_repository")
    dto_mod = _import(generated_dir, "policy_dtos")

    user_repo = user_repo_mod.UserRepository(session)
    user = await user_repo.create(user_dto_mod.UserCreate(name="Owner", email="owner@test.com"))

    repo = repo_mod.PolicyRepository(session)
    policy = await repo.create(dto_mod.PolicyCreate(
        holder_id=user.id,
        policy_number="POL-001",
        premium=100.50,
    ))
    assert policy.id is not None
    assert policy.policy_number == "POL-001"

    # Non-soft-deletable: delete is a hard delete
    result = await repo.delete(policy.id)
    assert result is True
    assert await repo.get_by_id(policy.id) is None


# ─── TenantPolicy CRUD (composite PK) ────────────────────────────────────


async def test_tenant_policy_composite_pk_crud(generated_dir, session):
    repo_mod = _import(generated_dir, "tenant_policy_repository")
    dto_mod = _import(generated_dir, "tenant_policy_dtos")

    repo = repo_mod.TenantPolicyRepository(session)
    tp = await repo.create(dto_mod.TenantPolicyCreate(
        tenant_id=1,
        policy_number="TP-001",
        tenant_name="Acme",
        premium=500.00,
    ))
    assert tp.tenant_id == 1
    assert tp.policy_number == "TP-001"

    found = await repo.get_by_id(1, "TP-001")
    assert found is not None
    assert found.tenant_name == "Acme"

    updated = await repo.update(dto_mod.TenantPolicyUpdate(
        tenant_id=1,
        policy_number="TP-001",
        tenant_name="Acme Corp",
    ))
    assert updated is not None
    assert updated.tenant_name == "Acme Corp"

    result = await repo.delete(1, "TP-001")
    assert result is True
    assert await repo.get_by_id(1, "TP-001") is None
