"""Tests for DTO generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.dto_generator import generate_dtos

_MODELS_FILE = Path(__file__).parent / "test_models" / "models.py"


def _get_model(models: list[ModelIR], class_name: str) -> ModelIR:
    for m in models:
        if m.class_name == class_name:
            return m
    raise ValueError(f"Model {class_name!r} not found")


@pytest.fixture(scope="module")
def model_irs() -> list[ModelIR]:
    return discover_models(str(_MODELS_FILE))


@pytest.fixture
def user_dto_content(model_irs: list[ModelIR], tmp_path: Path) -> str:
    user = _get_model(model_irs, "User")
    generate_dtos(user, tmp_path)
    return (tmp_path / "user_dtos.py").read_text()


@pytest.fixture
def tenant_policy_dto_content(model_irs: list[ModelIR], tmp_path: Path) -> str:
    tp = _get_model(model_irs, "TenantPolicy")
    generate_dtos(tp, tmp_path)
    return (tmp_path / "tenant_policy_dtos.py").read_text()


# ---- UserCreate tests -------------------------------------------------------


def test_user_create_dto_has_required_fields(user_dto_content: str):
    """name and email are required fields in UserCreate."""
    assert "name: str" in user_dto_content
    assert "email: str" in user_dto_content


def test_user_create_dto_excludes_autoincrement_pk(user_dto_content: str):
    """Autoincrement PK 'id' is not in the create DTO."""
    create_block = user_dto_content.split("class UserCreate")[1].split(
        "class UserUpdate"
    )[0]
    lines = create_block.strip().splitlines()
    field_names = [
        line.strip().split(":")[0]
        for line in lines
        if ":" in line and not line.strip().startswith("#")
    ]
    assert "id" not in field_names


def test_user_create_dto_excludes_soft_delete_column(user_dto_content: str):
    """deleted_at is not present in the create DTO."""
    create_block = user_dto_content.split("class UserCreate")[1].split(
        "class UserUpdate"
    )[0]
    assert "deleted_at" not in create_block


def test_user_create_dto_optional_fields(user_dto_content: str):
    """bio, role, is_active, created_at are optional (with | None = None) in create DTO."""
    create_block = user_dto_content.split("class UserCreate")[1].split(
        "class UserUpdate"
    )[0]
    for field in ("bio", "role", "is_active", "created_at"):
        assert f"{field}:" in create_block
        for line in create_block.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{field}:"):
                assert (
                    "| None = None" in stripped
                ), f"{field} should be optional with '| None = None'"
                break


# ---- UserUpdate tests -------------------------------------------------------


def test_user_update_dto_pk_required(user_dto_content: str):
    """id is required in the update DTO."""
    update_block = user_dto_content.split("class UserUpdate")[1]
    assert "id: int" in update_block


def test_user_update_dto_excludes_created_at(user_dto_content: str):
    """created_at is not present in the update DTO."""
    update_block = user_dto_content.split("class UserUpdate")[1]
    lines = update_block.strip().splitlines()
    field_names = [
        line.strip().split(":")[0]
        for line in lines
        if ":" in line and not line.strip().startswith("#")
    ]
    assert "created_at" not in field_names


def test_user_update_dto_optional_fields(user_dto_content: str):
    """Non-PK fields in the update DTO are optional."""
    update_block = user_dto_content.split("class UserUpdate")[1]
    for field in ("name", "email", "bio", "role", "is_active"):
        for line in update_block.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{field}:"):
                assert (
                    "| None = None" in stripped
                ), f"{field} should be optional in update DTO"
                break


# ---- TenantPolicy DTO tests ------------------------------------------------


def test_tenant_policy_create_dto(tenant_policy_dto_content: str):
    """Composite PK: policy_number required, tenant_name required."""
    create_block = tenant_policy_dto_content.split("class TenantPolicyCreate")[1].split(
        "class TenantPolicyUpdate"
    )[0]
    assert "policy_number: str" in create_block
    assert "tenant_name: str" in create_block


def test_tenant_policy_update_dto_composite_pk(tenant_policy_dto_content: str):
    """Both PKs are required in the update DTO."""
    update_block = tenant_policy_dto_content.split("class TenantPolicyUpdate")[1]
    assert "policy_number: str" in update_block


# ---- Header test ------------------------------------------------------------


def test_dto_file_has_header(user_dto_content: str):
    """Generated file starts with auto-generated header."""
    assert user_dto_content.startswith("# AUTO-GENERATED by RepoGen")
