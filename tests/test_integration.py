"""End-to-end integration tests using actual async SQLite database."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.test_models.models import Base
from repogen.introspection.engine import discover_models
from repogen.generators.dto_generator import generate_dtos
from repogen.generators.filter_generator import generate_filters
from repogen.generators.loading_generator import generate_load_options
from repogen.generators.repo_generator import generate_repository
from repogen.generators.internals_generator import generate_internals


@pytest.fixture(scope="module")
def generated_dir(tmp_path_factory):
    """Generate all code to a temporary directory and make it importable."""
    output = tmp_path_factory.mktemp("generated")
    models_path = Path(__file__).parent / "test_models" / "models.py"
    model_irs = discover_models(str(models_path))

    # Create __init__.py so the directory is a package
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

    # Make generated code importable
    if str(output.parent) not in sys.path:
        sys.path.insert(0, str(output.parent))

    # The test models directory also needs to be on sys.path so the generated
    # repo can do `from models import User` (module_path will be "models").
    test_models_dir = Path(__file__).parent / "test_models"
    if str(test_models_dir) not in sys.path:
        sys.path.insert(0, str(test_models_dir))

    return output


@pytest.fixture
async def session():
    """Create a fresh in-memory SQLite database with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helper to import generated modules
# ---------------------------------------------------------------------------

def _import_gen(generated_dir, module_suffix: str):
    """Import a generated module by suffix, e.g. 'user_repository'."""
    mod_name = f"{generated_dir.name}.{module_suffix}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_create_and_get_user(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    UserRepository = repo_mod.UserRepository
    UserCreate = dto_mod.UserCreate

    repo = UserRepository(session)
    user = await repo.create(UserCreate(name="Alice", email="alice@example.com"))
    assert user.id is not None

    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.name == "Alice"
    assert found.email == "alice@example.com"


async def test_create_many_users(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    UserRepository = repo_mod.UserRepository
    UserCreate = dto_mod.UserCreate

    repo = UserRepository(session)
    users = await repo.create_many([
        UserCreate(name="Bob", email="bob@example.com"),
        UserCreate(name="Carol", email="carol@example.com"),
    ])
    assert len(users) == 2
    assert all(u.id is not None for u in users)


async def test_user_soft_delete(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Dave", email="dave@example.com"))

    deleted = await repo.delete(user.id)
    assert deleted is True

    # Not found without include_deleted
    found = await repo.get_by_id(user.id)
    assert found is None

    # Found with include_deleted
    found = await repo.get_by_id(user.id, include_deleted=True)
    assert found is not None
    assert found.deleted_at is not None


async def test_user_restore(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Eve", email="eve@example.com"))

    await repo.delete(user.id)
    restored = await repo.restore(user.id)
    assert restored is not None
    assert restored.deleted_at is None

    # Should be found again without include_deleted
    found = await repo.get_by_id(user.id)
    assert found is not None


async def test_user_hard_delete(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Frank", email="frank@example.com"))

    result = await repo.hard_delete(user.id)
    assert result is True

    # Permanently gone even with include_deleted
    found = await repo.get_by_id(user.id, include_deleted=True)
    assert found is None


async def test_user_get_by_email(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Grace", email="grace@example.com"))

    found = await repo.get_by_email("grace@example.com")
    assert found is not None
    assert found.name == "Grace"

    not_found = await repo.get_by_email("nobody@example.com")
    assert not_found is None


async def test_user_count_and_exists(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")
    filter_mod = _import_gen(generated_dir, "user_filters")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Hank", email="hank@example.com"))
    await repo.create(dto_mod.UserCreate(name="Ivy", email="ivy@example.com"))

    count = await repo.count()
    assert count == 2

    UserFilter = filter_mod.UserFilter
    StringFilter = filter_mod.StringFilter

    exists = await repo.exists(filters=UserFilter(name=StringFilter(eq="Hank")))
    assert exists is True

    exists = await repo.exists(filters=UserFilter(name=StringFilter(eq="Nobody")))
    assert exists is False


async def test_user_filter_by_name(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")
    filter_mod = _import_gen(generated_dir, "user_filters")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Jack", email="jack@example.com"))
    await repo.create(dto_mod.UserCreate(name="Jill", email="jill@example.com"))

    UserFilter = filter_mod.UserFilter
    StringFilter = filter_mod.StringFilter

    results = await repo.get_many(filters=UserFilter(name=StringFilter(eq="Jack")))
    assert len(results) == 1
    assert results[0].name == "Jack"


async def test_user_filter_by_active(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")
    filter_mod = _import_gen(generated_dir, "user_filters")

    repo = repo_mod.UserRepository(session)
    await repo.create(dto_mod.UserCreate(name="Kate", email="kate@example.com", is_active=True))
    await repo.create(dto_mod.UserCreate(name="Leo", email="leo@example.com", is_active=False))

    UserFilter = filter_mod.UserFilter
    BoolFilter = filter_mod.BoolFilter

    active = await repo.get_many(filters=UserFilter(is_active=BoolFilter(eq=True)))
    assert all(u.is_active for u in active)

    inactive = await repo.get_many(filters=UserFilter(is_active=BoolFilter(eq=False)))
    assert all(not u.is_active for u in inactive)
    assert len(inactive) == 1


async def test_user_update(generated_dir, session):
    repo_mod = _import_gen(generated_dir, "user_repository")
    dto_mod = _import_gen(generated_dir, "user_dtos")

    repo = repo_mod.UserRepository(session)
    user = await repo.create(dto_mod.UserCreate(name="Mike", email="mike@example.com"))

    updated = await repo.update(dto_mod.UserUpdate(id=user.id, name="Michael"))
    assert updated is not None
    assert updated.name == "Michael"
    assert updated.email == "mike@example.com"  # unchanged


async def test_policy_create_and_delete(generated_dir, session):
    """Non-soft-deletable model: delete is a hard delete."""
    user_repo_mod = _import_gen(generated_dir, "user_repository")
    user_dto_mod = _import_gen(generated_dir, "user_dtos")
    policy_repo_mod = _import_gen(generated_dir, "policy_repository")
    policy_dto_mod = _import_gen(generated_dir, "policy_dtos")

    user_repo = user_repo_mod.UserRepository(session)
    user = await user_repo.create(user_dto_mod.UserCreate(name="Nora", email="nora@example.com"))

    from decimal import Decimal
    policy_repo = policy_repo_mod.PolicyRepository(session)
    policy = await policy_repo.create(policy_dto_mod.PolicyCreate(
        holder_id=user.id,
        policy_number="POL-001",
        premium=Decimal("100.00"),
    ))
    assert policy.id is not None

    # Delete is a hard delete for Policy (no soft delete)
    result = await policy_repo.delete(policy.id)
    assert result is True

    # Permanently gone
    found = await policy_repo.get_by_id(policy.id)
    assert found is None


async def test_tenant_policy_composite_pk_crud(generated_dir, session):
    """Composite PK CRUD operations for TenantPolicy."""
    tp_repo_mod = _import_gen(generated_dir, "tenant_policy_repository")
    tp_dto_mod = _import_gen(generated_dir, "tenant_policy_dtos")

    from decimal import Decimal
    repo = tp_repo_mod.TenantPolicyRepository(session)

    # Create
    tp = await repo.create(tp_dto_mod.TenantPolicyCreate(
        tenant_id=1,
        policy_number="TP-001",
        tenant_name="Acme Corp",
        premium=Decimal("500.00"),
    ))
    assert tp.tenant_id == 1
    assert tp.policy_number == "TP-001"

    # Get by composite PK
    found = await repo.get_by_id(1, "TP-001")
    assert found is not None
    assert found.tenant_name == "Acme Corp"

    # Update
    updated = await repo.update(tp_dto_mod.TenantPolicyUpdate(
        tenant_id=1,
        policy_number="TP-001",
        tenant_name="Acme Inc",
    ))
    assert updated is not None
    assert updated.tenant_name == "Acme Inc"

    # Delete
    result = await repo.delete(1, "TP-001")
    assert result is True

    found = await repo.get_by_id(1, "TP-001")
    assert found is None
