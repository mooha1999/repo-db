"""Tests for DTO generation.

These tests run the CLI, compile every generated DTO file, import the classes,
and verify their structure through actual Pydantic model inspection.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Syntax / compile checks
# ---------------------------------------------------------------------------


def test_user_dtos_compile(generated_package):
    """user_dtos.py has no syntax errors."""
    path = generated_package / "user_dtos.py"
    assert path.exists(), "user_dtos.py was not generated"
    py_compile.compile(str(path), doraise=True)


def test_tenant_policy_dtos_compile(generated_package):
    """tenant_policy_dtos.py has no syntax errors."""
    path = generated_package / "tenant_policy_dtos.py"
    assert path.exists(), "tenant_policy_dtos.py was not generated"
    py_compile.compile(str(path), doraise=True)


def test_policy_dtos_compile(generated_package):
    """policy_dtos.py has no syntax errors."""
    path = generated_package / "policy_dtos.py"
    assert path.exists(), "policy_dtos.py was not generated"
    py_compile.compile(str(path), doraise=True)


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------


def test_user_dtos_importable(gen_import):
    """user_dtos module can be imported and contains expected classes."""
    mod = gen_import("user_dtos")
    assert hasattr(mod, "UserCreate")
    assert hasattr(mod, "UserUpdate")
    assert issubclass(mod.UserCreate, BaseModel)
    assert issubclass(mod.UserUpdate, BaseModel)


def test_tenant_policy_dtos_importable(gen_import):
    mod = gen_import("tenant_policy_dtos")
    assert hasattr(mod, "TenantPolicyCreate")
    assert hasattr(mod, "TenantPolicyUpdate")
    assert issubclass(mod.TenantPolicyCreate, BaseModel)
    assert issubclass(mod.TenantPolicyUpdate, BaseModel)


# ---------------------------------------------------------------------------
# UserCreate field logic
# ---------------------------------------------------------------------------


def test_user_create_required_fields(gen_import):
    """name and email are required (no default) in UserCreate."""
    UserCreate = gen_import("user_dtos").UserCreate
    fields = UserCreate.model_fields
    assert "name" in fields
    assert "email" in fields
    assert fields["name"].is_required()
    assert fields["email"].is_required()


def test_user_create_excludes_autoincrement_pk(gen_import):
    """Autoincrement PK 'id' is excluded from UserCreate."""
    UserCreate = gen_import("user_dtos").UserCreate
    assert "id" not in UserCreate.model_fields


def test_user_create_excludes_soft_delete_column(gen_import):
    """deleted_at is excluded from UserCreate."""
    UserCreate = gen_import("user_dtos").UserCreate
    assert "deleted_at" not in UserCreate.model_fields


def test_user_create_optional_fields(gen_import):
    """bio, role, is_active, created_at are optional in UserCreate."""
    UserCreate = gen_import("user_dtos").UserCreate
    for field_name in ("bio", "role", "is_active", "created_at"):
        assert field_name in UserCreate.model_fields, f"{field_name} missing"
        assert not UserCreate.model_fields[field_name].is_required(), (
            f"{field_name} should be optional"
        )


def test_user_create_instantiation(gen_import):
    """UserCreate can be instantiated with only required fields."""
    UserCreate = gen_import("user_dtos").UserCreate
    dto = UserCreate(name="Alice", email="alice@example.com")
    assert dto.name == "Alice"
    assert dto.email == "alice@example.com"


# ---------------------------------------------------------------------------
# UserUpdate field logic
# ---------------------------------------------------------------------------


def test_user_update_pk_required(gen_import):
    """id is required in UserUpdate."""
    UserUpdate = gen_import("user_dtos").UserUpdate
    assert "id" in UserUpdate.model_fields
    assert UserUpdate.model_fields["id"].is_required()


def test_user_update_excludes_created_at(gen_import):
    """created_at is excluded from UserUpdate."""
    UserUpdate = gen_import("user_dtos").UserUpdate
    assert "created_at" not in UserUpdate.model_fields


def test_user_update_optional_non_pk_fields(gen_import):
    """Non-PK fields are optional in UserUpdate."""
    UserUpdate = gen_import("user_dtos").UserUpdate
    for field_name in ("name", "email", "bio", "role", "is_active"):
        assert field_name in UserUpdate.model_fields, f"{field_name} missing"
        assert not UserUpdate.model_fields[field_name].is_required(), (
            f"{field_name} should be optional in update"
        )


def test_user_update_partial_instantiation(gen_import):
    """UserUpdate can be instantiated with just the PK."""
    UserUpdate = gen_import("user_dtos").UserUpdate
    dto = UserUpdate(id=1)
    assert dto.id == 1


# ---------------------------------------------------------------------------
# TenantPolicy DTOs (composite PK)
# ---------------------------------------------------------------------------


def test_tenant_policy_create_has_all_pk_fields(gen_import):
    """Both PKs (tenant_id, policy_number) are present in TenantPolicyCreate."""
    TPC = gen_import("tenant_policy_dtos").TenantPolicyCreate
    assert "tenant_id" in TPC.model_fields
    assert "policy_number" in TPC.model_fields


def test_tenant_policy_update_pk_required(gen_import):
    """Both PKs are required in TenantPolicyUpdate."""
    TPU = gen_import("tenant_policy_dtos").TenantPolicyUpdate
    assert TPU.model_fields["tenant_id"].is_required()
    assert TPU.model_fields["policy_number"].is_required()


def test_tenant_policy_create_instantiation(gen_import):
    """TenantPolicyCreate can be instantiated and round-tripped."""
    from decimal import Decimal
    TPC = gen_import("tenant_policy_dtos").TenantPolicyCreate
    dto = TPC(tenant_id=1, policy_number="TP-001", tenant_name="Acme", premium=Decimal("100"))
    assert dto.tenant_id == 1
    data = dto.model_dump()
    assert "tenant_id" in data


# ---------------------------------------------------------------------------
# Header check
# ---------------------------------------------------------------------------


def test_dto_file_has_header(generated_package):
    """Generated file starts with auto-generated header."""
    content = (generated_package / "user_dtos.py").read_text()
    assert content.startswith("# AUTO-GENERATED by RepoGen")
