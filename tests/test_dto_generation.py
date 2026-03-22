"""Tests for DTO generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.dto_generator import generate_dtos

_MODELS_FILE = Path(__file__).parent / "test_models" / "models.py"


def _find_model(models: list[ModelIR], class_name: str) -> ModelIR:
    for m in models:
        if m.class_name == class_name:
            return m
    raise ValueError(f"Model {class_name!r} not found")


@pytest.fixture(scope="module")
def all_models() -> list[ModelIR]:
    return discover_models(str(_MODELS_FILE))


@pytest.fixture
def user_dto_content(all_models, tmp_path):
    user = _find_model(all_models, "User")
    generate_dtos(user, tmp_path)
    return (tmp_path / "user_dtos.py").read_text()


@pytest.fixture
def tenant_policy_dto_content(all_models, tmp_path):
    tp = _find_model(all_models, "TenantPolicy")
    generate_dtos(tp, tmp_path)
    return (tmp_path / "tenant_policy_dtos.py").read_text()


# ------------------------------------------------------------------
# UserCreate DTO
# ------------------------------------------------------------------

def test_user_create_dto_has_required_fields(user_dto_content):
    """name and email should be required fields (no default)."""
    assert "name: str" in user_dto_content
    assert "email: str" in user_dto_content


def test_user_create_dto_excludes_autoincrement_pk(user_dto_content):
    """id should not appear in UserCreate since it is autoincrement."""
    # Extract the UserCreate class body
    create_start = user_dto_content.index("class UserCreate")
    update_start = user_dto_content.index("class UserUpdate")
    create_body = user_dto_content[create_start:update_start]
    # 'id' should not appear as a field
    lines = create_body.split("\n")
    field_lines = [l.strip() for l in lines if ":" in l and not l.strip().startswith("class")]
    field_names = [l.split(":")[0].strip() for l in field_lines]
    assert "id" not in field_names


def test_user_create_dto_excludes_soft_delete_column(user_dto_content):
    """deleted_at should not appear in UserCreate."""
    create_start = user_dto_content.index("class UserCreate")
    update_start = user_dto_content.index("class UserUpdate")
    create_body = user_dto_content[create_start:update_start]
    assert "deleted_at" not in create_body


def test_user_create_dto_optional_fields(user_dto_content):
    """bio, role, is_active, created_at should be optional with | None = None."""
    for field in ("bio", "role", "is_active", "created_at"):
        assert f"{field}:" in user_dto_content
    # They should have " | None = None"
    create_start = user_dto_content.index("class UserCreate")
    update_start = user_dto_content.index("class UserUpdate")
    create_body = user_dto_content[create_start:update_start]
    for field in ("bio", "role", "is_active", "created_at"):
        # Find the line with this field
        for line in create_body.split("\n"):
            stripped = line.strip()
            if stripped.startswith(f"{field}:"):
                assert "| None = None" in stripped, f"{field} should be optional: {stripped}"
                break


# ------------------------------------------------------------------
# UserUpdate DTO
# ------------------------------------------------------------------

def test_user_update_dto_pk_required(user_dto_content):
    """id should be required in UserUpdate."""
    update_start = user_dto_content.index("class UserUpdate")
    update_body = user_dto_content[update_start:]
    # id should appear without = None
    for line in update_body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("id:"):
            assert "= None" not in stripped, "id should be required in update DTO"
            break


def test_user_update_dto_excludes_created_at(user_dto_content):
    """created_at should not appear in UserUpdate."""
    update_start = user_dto_content.index("class UserUpdate")
    update_body = user_dto_content[update_start:]
    lines = update_body.split("\n")
    field_lines = [l.strip() for l in lines if ":" in l and not l.strip().startswith("class")]
    field_names = [l.split(":")[0].strip() for l in field_lines]
    assert "created_at" not in field_names


def test_user_update_dto_optional_fields(user_dto_content):
    """Non-PK fields should be optional in UserUpdate."""
    update_start = user_dto_content.index("class UserUpdate")
    update_body = user_dto_content[update_start:]
    for field in ("name", "email", "bio", "role", "is_active"):
        for line in update_body.split("\n"):
            stripped = line.strip()
            if stripped.startswith(f"{field}:"):
                assert "| None = None" in stripped, f"{field} should be optional in update: {stripped}"
                break


# ------------------------------------------------------------------
# TenantPolicy DTOs (composite PK)
# ------------------------------------------------------------------

def test_tenant_policy_create_dto(tenant_policy_dto_content):
    """Composite PK: tenant_id and policy_number should be required in create."""
    create_start = tenant_policy_dto_content.index("class TenantPolicyCreate")
    update_start = tenant_policy_dto_content.index("class TenantPolicyUpdate")
    create_body = tenant_policy_dto_content[create_start:update_start]
    # tenant_id: int  (required, no default)
    assert "tenant_id:" in create_body
    assert "policy_number:" in create_body


def test_tenant_policy_update_dto_composite_pk(tenant_policy_dto_content):
    """Both PKs should be required in update DTO."""
    update_start = tenant_policy_dto_content.index("class TenantPolicyUpdate")
    update_body = tenant_policy_dto_content[update_start:]
    for field in ("tenant_id", "policy_number"):
        found = False
        for line in update_body.split("\n"):
            stripped = line.strip()
            if stripped.startswith(f"{field}:"):
                assert "= None" not in stripped, f"{field} should be required in update"
                found = True
                break
        assert found, f"{field} not found in update DTO"


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------

def test_dto_file_has_header(user_dto_content):
    """Generated file should start with the auto-generated header."""
    assert user_dto_content.startswith("# AUTO-GENERATED by RepoGen")
