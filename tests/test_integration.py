"""End-to-end integration tests.

These tests use the CLI-generated code (via the shared ``generated_package``
fixture), import it, and run it against an in-memory SQLite database to
verify that the generated repositories, DTOs, and filters actually work.
"""
from __future__ import annotations

import json
import py_compile
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Compile every generated file
# ---------------------------------------------------------------------------


def test_all_generated_files_compile(generated_package):
    """Every .py file under the generated package compiles without errors."""
    py_files = list(generated_package.rglob("*.py"))
    assert len(py_files) > 0, "No .py files found in generated output"
    for path in py_files:
        py_compile.compile(str(path), doraise=True)


# ---------------------------------------------------------------------------
# Pyright strict type check
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("pyright") is None, reason="pyright not installed")
def test_generated_code_passes_pyright_strict(generated_package, test_models_file):
    """All generated code passes pyright in strict mode with zero errors."""
    # Write a pyrightconfig.json next to the generated package
    config_dir = generated_package.parent
    config = {
        "include": [str(generated_package)],
        "extraPaths": [
            str(test_models_file.parent),
            str(Path(__file__).resolve().parent.parent / "src"),
        ],
        "typeCheckingMode": "strict",
        "pythonVersion": "3.11",
    }
    config_path = config_dir / "pyrightconfig.json"
    config_path.write_text(json.dumps(config))

    result = subprocess.run(
        ["pyright", "--outputjson"],
        capture_output=True,
        text=True,
        cwd=str(config_dir),
        timeout=60,
    )

    diagnostics = json.loads(result.stdout) if result.stdout else {}
    error_count = diagnostics.get("summary", {}).get("errorCount", -1)

    if error_count != 0:
        # Build a readable message from the diagnostics
        lines = []
        for diag in diagnostics.get("generalDiagnostics", []):
            f = diag.get("file", "?")
            r = diag.get("range", {}).get("start", {})
            msg = diag.get("message", "")
            rule = diag.get("rule", "")
            lines.append(f"  {f}:{r.get('line', '?')} - {msg} ({rule})")
        detail = "\n".join(lines[:30])
        pytest.fail(f"pyright strict found {error_count} error(s):\n{detail}")


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


async def test_create_and_get_user(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    user = await repo.create(dto_mod.UserCreate(name="Alice", email="alice@example.com"))
    assert user.id is not None

    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.name == "Alice"
    assert found.email == "alice@example.com"


async def test_create_many_users(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    users = await repo.create_many([
        dto_mod.UserCreate(name="Bob", email="bob@example.com"),
        dto_mod.UserCreate(name="Carol", email="carol@example.com"),
    ])
    assert len(users) == 2
    assert all(u.id is not None for u in users)


async def test_user_update(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    user = await repo.create(dto_mod.UserCreate(name="Mike", email="mike@example.com"))

    updated = await repo.update(dto_mod.UserUpdate(id=user.id, name="Michael"))
    assert updated is not None
    assert updated.name == "Michael"
    assert updated.email == "mike@example.com"  # unchanged


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


async def test_user_soft_delete(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    user = await repo.create(dto_mod.UserCreate(name="Dave", email="dave@example.com"))

    deleted = await repo.delete(user.id)
    assert deleted is True

    # Not visible without include_deleted
    assert await repo.get_by_id(user.id) is None

    # Visible with include_deleted
    found = await repo.get_by_id(user.id, include_deleted=True)
    assert found is not None
    assert found.deleted_at is not None


async def test_user_restore(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    user = await repo.create(dto_mod.UserCreate(name="Eve", email="eve@example.com"))

    await repo.delete(user.id)
    restored = await repo.restore(user.id)
    assert restored is not None
    assert restored.deleted_at is None

    # Found again normally
    assert await repo.get_by_id(user.id) is not None


async def test_user_hard_delete(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    user = await repo.create(dto_mod.UserCreate(name="Frank", email="frank@example.com"))

    result = await repo.hard_delete(user.id)
    assert result is True

    # Permanently gone
    assert await repo.get_by_id(user.id, include_deleted=True) is None


# ---------------------------------------------------------------------------
# Unique column lookup
# ---------------------------------------------------------------------------


async def test_user_get_by_email(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Grace", email="grace@example.com"))

    found = await repo.get_by_email("grace@example.com")
    assert found is not None
    assert found.name == "Grace"

    assert await repo.get_by_email("nobody@example.com") is None


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


async def test_user_filter_by_name(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")
    filter_mod = gen_import("user_filters")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Jack", email="jack@example.com"))
    await repo.create(dto_mod.UserCreate(name="Jill", email="jill@example.com"))

    results = await repo.get_many(
        filters=filter_mod.UserFilter(name=filter_mod.StringFilter(eq="Jack"))
    )
    assert len(results) == 1
    assert results[0].name == "Jack"


async def test_user_filter_by_active(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")
    filter_mod = gen_import("user_filters")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Kate", email="kate@example.com", is_active=True))
    await repo.create(dto_mod.UserCreate(name="Leo", email="leo@example.com", is_active=False))

    active = await repo.get_many(
        filters=filter_mod.UserFilter(is_active=filter_mod.BoolFilter(eq=True))
    )
    assert all(u.is_active for u in active)

    inactive = await repo.get_many(
        filters=filter_mod.UserFilter(is_active=filter_mod.BoolFilter(eq=False))
    )
    assert len(inactive) == 1
    assert not inactive[0].is_active


async def test_user_filter_like(gen_import, async_session):
    """String like filter works."""
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")
    filter_mod = gen_import("user_filters")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Anna", email="anna@example.com"))
    await repo.create(dto_mod.UserCreate(name="Andrew", email="andrew@example.com"))
    await repo.create(dto_mod.UserCreate(name="Zach", email="zach@example.com"))

    results = await repo.get_many(
        filters=filter_mod.UserFilter(name=filter_mod.StringFilter(like="An%"))
    )
    assert len(results) == 2
    assert all(r.name.startswith("An") for r in results)


# ---------------------------------------------------------------------------
# Count and exists
# ---------------------------------------------------------------------------


async def test_user_count_and_exists(gen_import, async_session):
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")
    filter_mod = gen_import("user_filters")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Hank", email="hank@example.com"))
    await repo.create(dto_mod.UserCreate(name="Ivy", email="ivy@example.com"))

    assert await repo.count() == 2

    exists = await repo.exists(
        filters=filter_mod.UserFilter(name=filter_mod.StringFilter(eq="Hank"))
    )
    assert exists is True

    not_exists = await repo.exists(
        filters=filter_mod.UserFilter(name=filter_mod.StringFilter(eq="Nobody"))
    )
    assert not_exists is False


# ---------------------------------------------------------------------------
# Order by
# ---------------------------------------------------------------------------


async def test_user_order_by(gen_import, async_session):
    """get_many order_by sorts results correctly."""
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Charlie", email="charlie@example.com"))
    await repo.create(dto_mod.UserCreate(name="Alice", email="alice_sort@example.com"))
    await repo.create(dto_mod.UserCreate(name="Bob", email="bob_sort@example.com"))

    results = await repo.get_many(order_by=["name"])
    names = [r.name for r in results]
    assert names == sorted(names)

    results_desc = await repo.get_many(order_by=["-name"])
    names_desc = [r.name for r in results_desc]
    assert names_desc == sorted(names_desc, reverse=True)


# ---------------------------------------------------------------------------
# Limit and offset
# ---------------------------------------------------------------------------


async def test_user_limit_offset(gen_import, async_session):
    """get_many limit and offset work correctly."""
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")

    repo = repo_mod.UserRepository(async_session)
    for i in range(5):
        await repo.create(dto_mod.UserCreate(name=f"User{i}", email=f"user{i}@example.com"))

    all_users = await repo.get_many()
    assert len(all_users) == 5

    limited = await repo.get_many(limit=3)
    assert len(limited) == 3

    offset = await repo.get_many(limit=2, offset=3)
    assert len(offset) == 2


# ---------------------------------------------------------------------------
# Non-soft-deletable model (Policy)
# ---------------------------------------------------------------------------


async def test_policy_create_and_hard_delete(gen_import, async_session):
    """Policy has no soft delete — delete permanently removes the record."""
    user_repo = gen_import("user_repository").UserRepository(async_session)
    user_dto = gen_import("user_dtos").UserCreate
    policy_repo = gen_import("policy_repository").PolicyRepository(async_session)
    policy_dto = gen_import("policy_dtos").PolicyCreate

    user = await user_repo.create(user_dto(name="Nora", email="nora@example.com"))
    policy = await policy_repo.create(policy_dto(
        holder_id=user.id,
        policy_number="POL-001",
        premium=Decimal("100.00"),
    ))
    assert policy.id is not None

    result = await policy_repo.delete(policy.id)
    assert result is True

    assert await policy_repo.get_by_id(policy.id) is None


# ---------------------------------------------------------------------------
# Composite PK (TenantPolicy)
# ---------------------------------------------------------------------------


async def test_tenant_policy_composite_pk_crud(gen_import, async_session):
    """Full CRUD cycle on a model with composite primary key."""
    tp_repo = gen_import("tenant_policy_repository").TenantPolicyRepository(async_session)
    tp_dto = gen_import("tenant_policy_dtos")

    # Create
    tp = await tp_repo.create(tp_dto.TenantPolicyCreate(
        tenant_id=1,
        policy_number="TP-001",
        tenant_name="Acme Corp",
        premium=Decimal("500.00"),
    ))
    assert tp.tenant_id == 1
    assert tp.policy_number == "TP-001"

    # Get by composite PK
    found = await tp_repo.get_by_id(1, "TP-001")
    assert found is not None
    assert found.tenant_name == "Acme Corp"

    # Update
    updated = await tp_repo.update(tp_dto.TenantPolicyUpdate(
        tenant_id=1,
        policy_number="TP-001",
        tenant_name="Acme Inc",
    ))
    assert updated is not None
    assert updated.tenant_name == "Acme Inc"

    # Delete
    result = await tp_repo.delete(1, "TP-001")
    assert result is True
    assert await tp_repo.get_by_id(1, "TP-001") is None


# ---------------------------------------------------------------------------
# get_one
# ---------------------------------------------------------------------------


async def test_get_one(gen_import, async_session):
    """get_one returns a single match or None."""
    repo_mod = gen_import("user_repository")
    dto_mod = gen_import("user_dtos")
    filter_mod = gen_import("user_filters")

    repo = repo_mod.UserRepository(async_session)
    await repo.create(dto_mod.UserCreate(name="Solo", email="solo@example.com"))

    found = await repo.get_one(
        filters=filter_mod.UserFilter(name=filter_mod.StringFilter(eq="Solo"))
    )
    assert found is not None
    assert found.name == "Solo"

    not_found = await repo.get_one(
        filters=filter_mod.UserFilter(name=filter_mod.StringFilter(eq="Ghost"))
    )
    assert not_found is None


# ---------------------------------------------------------------------------
# Internals compile and import
# ---------------------------------------------------------------------------


def test_internals_compile(generated_package):
    """All internal utility modules compile without errors."""
    internals = generated_package / "_internals"
    assert internals.is_dir(), "_internals directory not generated"
    for py_file in internals.glob("*.py"):
        py_compile.compile(str(py_file), doraise=True)


def test_internals_importable(gen_import):
    """Internal utility modules can be imported."""
    filter_utils = gen_import("_internals.filter_utils")
    assert hasattr(filter_utils, "apply_filters")

    loading_utils = gen_import("_internals.loading_utils")
    assert hasattr(loading_utils, "apply_load_options")

    soft_delete = gen_import("_internals.soft_delete")
    assert hasattr(soft_delete, "apply_soft_delete_filter")


# ---------------------------------------------------------------------------
# __init__.py re-exports
# ---------------------------------------------------------------------------


def test_init_reexports(gen_import):
    """The generated __init__.py re-exports key classes."""
    pkg = gen_import("__init__")
    for cls in ("UserRepository", "UserCreate", "UserUpdate", "UserFilter", "UserLoadOptions"):
        assert hasattr(pkg, cls), f"__init__ missing re-export: {cls}"
