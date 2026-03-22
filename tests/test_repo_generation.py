"""Tests for repository generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.repo_generator import generate_repository

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
def user_repo_content(all_models, tmp_path):
    user = _find_model(all_models, "User")
    generate_repository(user, tmp_path, internals_path="generated", config={
        "generate_unique_lookups": True,
        "generate_hard_delete": True,
        "generate_restore": True,
    })
    return (tmp_path / "user_repository.py").read_text()


@pytest.fixture
def policy_repo_content(all_models, tmp_path):
    policy = _find_model(all_models, "Policy")
    generate_repository(policy, tmp_path, internals_path="generated", config={
        "generate_unique_lookups": True,
        "generate_hard_delete": True,
        "generate_restore": True,
    })
    return (tmp_path / "policy_repository.py").read_text()


@pytest.fixture
def tenant_policy_repo_content(all_models, tmp_path):
    tp = _find_model(all_models, "TenantPolicy")
    generate_repository(tp, tmp_path, internals_path="generated", config={
        "generate_unique_lookups": True,
        "generate_hard_delete": True,
        "generate_restore": True,
    })
    return (tmp_path / "tenant_policy_repository.py").read_text()


# ------------------------------------------------------------------
# User repo - soft delete
# ------------------------------------------------------------------

def test_user_repo_has_soft_delete_methods(user_repo_content):
    """User repo should have delete (soft), hard_delete, and restore methods."""
    assert "async def delete(" in user_repo_content
    assert "async def hard_delete(" in user_repo_content
    assert "async def restore(" in user_repo_content


def test_user_repo_include_deleted_param(user_repo_content):
    """get_by_id, get_many, and count should have include_deleted parameter."""
    # Check in get_by_id
    get_by_id_start = user_repo_content.index("async def get_by_id(")
    get_many_start = user_repo_content.index("async def get_many(")
    get_by_id_body = user_repo_content[get_by_id_start:get_many_start]
    assert "include_deleted" in get_by_id_body

    # Check in get_many
    get_one_start = user_repo_content.index("async def get_one(")
    get_many_body = user_repo_content[get_many_start:get_one_start]
    assert "include_deleted" in get_many_body

    # Check in count
    count_start = user_repo_content.index("async def count(")
    exists_start = user_repo_content.index("async def exists(")
    count_body = user_repo_content[count_start:exists_start]
    assert "include_deleted" in count_body


def test_user_repo_get_by_email(user_repo_content):
    """Unique column lookup method should be generated for email."""
    assert "async def get_by_email(" in user_repo_content


# ------------------------------------------------------------------
# Policy repo - no soft delete
# ------------------------------------------------------------------

def test_policy_repo_no_soft_delete(policy_repo_content):
    """Policy repo should not have hard_delete, restore, or include_deleted."""
    assert "async def hard_delete(" not in policy_repo_content
    assert "async def restore(" not in policy_repo_content
    assert "include_deleted" not in policy_repo_content


# ------------------------------------------------------------------
# TenantPolicy repo - composite PK
# ------------------------------------------------------------------

def test_tenant_policy_repo_composite_pk(tenant_policy_repo_content):
    """get_by_id should take both tenant_id and policy_number params."""
    get_by_id_start = tenant_policy_repo_content.index("async def get_by_id(")
    # Find the closing paren of get_by_id signature
    next_method = tenant_policy_repo_content.index("async def get_many(")
    signature = tenant_policy_repo_content[get_by_id_start:next_method]
    assert "tenant_id:" in signature
    assert "policy_number:" in signature


# ------------------------------------------------------------------
# CRUD methods
# ------------------------------------------------------------------

def test_repo_has_all_crud_methods(user_repo_content):
    """Repository should have all standard CRUD methods."""
    expected_methods = [
        "async def get_by_id(",
        "async def get_many(",
        "async def get_one(",
        "async def create(",
        "async def create_many(",
        "async def update(",
        "async def delete(",
        "async def count(",
        "async def exists(",
    ]
    for method in expected_methods:
        assert method in user_repo_content, f"Missing method: {method}"


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------

def test_repo_file_has_header(user_repo_content):
    """Generated file should start with the auto-generated header."""
    assert user_repo_content.startswith("# AUTO-GENERATED by RepoGen")
