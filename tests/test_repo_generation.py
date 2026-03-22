"""Tests for repository generation.

These tests compile and import generated repository modules, then verify
class structure, method signatures, and attribute presence through actual
inspection — not string matching.
"""
from __future__ import annotations

import asyncio
import inspect
import py_compile

import pytest


# ---------------------------------------------------------------------------
# Syntax / compile checks
# ---------------------------------------------------------------------------


def test_user_repo_compile(generated_package):
    """user_repository.py has no syntax errors."""
    path = generated_package / "user_repository.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


def test_policy_repo_compile(generated_package):
    """policy_repository.py has no syntax errors."""
    path = generated_package / "policy_repository.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


def test_tenant_policy_repo_compile(generated_package):
    """tenant_policy_repository.py has no syntax errors."""
    path = generated_package / "tenant_policy_repository.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------


def test_user_repo_importable(gen_import):
    """UserRepository can be imported."""
    mod = gen_import("user_repository")
    assert hasattr(mod, "UserRepository")


def test_policy_repo_importable(gen_import):
    """PolicyRepository can be imported."""
    mod = gen_import("policy_repository")
    assert hasattr(mod, "PolicyRepository")


def test_tenant_policy_repo_importable(gen_import):
    """TenantPolicyRepository can be imported."""
    mod = gen_import("tenant_policy_repository")
    assert hasattr(mod, "TenantPolicyRepository")


# ---------------------------------------------------------------------------
# CRUD methods present
# ---------------------------------------------------------------------------


_CRUD_METHODS = [
    "get_by_id", "get_many", "get_one",
    "create", "create_many",
    "update", "delete",
    "count", "exists",
]


def test_user_repo_has_all_crud_methods(gen_import):
    """UserRepository has all standard CRUD methods."""
    Repo = gen_import("user_repository").UserRepository
    for method in _CRUD_METHODS:
        assert hasattr(Repo, method), f"Missing method: {method}"
        assert asyncio.iscoroutinefunction(getattr(Repo, method)), (
            f"{method} should be async"
        )


def test_policy_repo_has_all_crud_methods(gen_import):
    """PolicyRepository has all standard CRUD methods."""
    Repo = gen_import("policy_repository").PolicyRepository
    for method in _CRUD_METHODS:
        assert hasattr(Repo, method), f"Missing method: {method}"


# ---------------------------------------------------------------------------
# Soft-delete methods
# ---------------------------------------------------------------------------


def test_user_repo_has_soft_delete_methods(gen_import):
    """User is soft-deletable: hard_delete and restore methods exist."""
    Repo = gen_import("user_repository").UserRepository
    assert hasattr(Repo, "hard_delete")
    assert hasattr(Repo, "restore")
    assert asyncio.iscoroutinefunction(Repo.hard_delete)
    assert asyncio.iscoroutinefunction(Repo.restore)


def test_user_repo_get_by_id_has_include_deleted(gen_import):
    """get_by_id on soft-deletable repo accepts include_deleted."""
    Repo = gen_import("user_repository").UserRepository
    sig = inspect.signature(Repo.get_by_id)
    assert "include_deleted" in sig.parameters


def test_user_repo_get_many_has_include_deleted(gen_import):
    """get_many on soft-deletable repo accepts include_deleted."""
    Repo = gen_import("user_repository").UserRepository
    sig = inspect.signature(Repo.get_many)
    assert "include_deleted" in sig.parameters


def test_user_repo_count_has_include_deleted(gen_import):
    """count on soft-deletable repo accepts include_deleted."""
    Repo = gen_import("user_repository").UserRepository
    sig = inspect.signature(Repo.count)
    assert "include_deleted" in sig.parameters


# ---------------------------------------------------------------------------
# Non-soft-delete repo (Policy)
# ---------------------------------------------------------------------------


def test_policy_repo_no_soft_delete_methods(gen_import):
    """Policy has no soft delete: hard_delete and restore should not exist."""
    Repo = gen_import("policy_repository").PolicyRepository
    assert not hasattr(Repo, "hard_delete")
    assert not hasattr(Repo, "restore")


def test_policy_repo_no_include_deleted(gen_import):
    """Policy get_by_id should not have include_deleted parameter."""
    Repo = gen_import("policy_repository").PolicyRepository
    sig = inspect.signature(Repo.get_by_id)
    assert "include_deleted" not in sig.parameters


# ---------------------------------------------------------------------------
# Unique column lookups
# ---------------------------------------------------------------------------


def test_user_repo_get_by_email(gen_import):
    """get_by_email is auto-generated for unique email column."""
    Repo = gen_import("user_repository").UserRepository
    assert hasattr(Repo, "get_by_email")
    assert asyncio.iscoroutinefunction(Repo.get_by_email)
    sig = inspect.signature(Repo.get_by_email)
    assert "email" in sig.parameters


# ---------------------------------------------------------------------------
# Composite PK (TenantPolicy)
# ---------------------------------------------------------------------------


def test_tenant_policy_get_by_id_composite_params(gen_import):
    """get_by_id on composite PK takes tenant_id and policy_number."""
    Repo = gen_import("tenant_policy_repository").TenantPolicyRepository
    sig = inspect.signature(Repo.get_by_id)
    params = list(sig.parameters.keys())
    # First param is self
    assert "tenant_id" in params
    assert "policy_number" in params


def test_tenant_policy_delete_composite_params(gen_import):
    """delete on composite PK takes tenant_id and policy_number."""
    Repo = gen_import("tenant_policy_repository").TenantPolicyRepository
    sig = inspect.signature(Repo.delete)
    params = list(sig.parameters.keys())
    assert "tenant_id" in params
    assert "policy_number" in params


# ---------------------------------------------------------------------------
# Header check
# ---------------------------------------------------------------------------


def test_repo_file_has_header(generated_package):
    """Generated file starts with auto-generated header."""
    content = (generated_package / "user_repository.py").read_text()
    assert content.startswith("# AUTO-GENERATED by RepoGen")
