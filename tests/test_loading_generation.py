"""Tests for load options generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.loading_generator import generate_load_options

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
def user_load_content(all_models, tmp_path):
    user = _find_model(all_models, "User")
    generate_load_options(user, all_models, tmp_path)
    return (tmp_path / "user_load_options.py").read_text()


@pytest.fixture
def claim_load_content(all_models, tmp_path):
    claim = _find_model(all_models, "Claim")
    generate_load_options(claim, all_models, tmp_path)
    return (tmp_path / "claim_load_options.py").read_text()


@pytest.fixture
def category_load_content(all_models, tmp_path):
    cat = _find_model(all_models, "Category")
    generate_load_options(cat, all_models, tmp_path)
    return (tmp_path / "category_load_options.py").read_text()


# ------------------------------------------------------------------
# User load options
# ------------------------------------------------------------------

def test_user_load_options_fields(user_load_content):
    """UserLoadOptions should have policies and profile fields."""
    assert "policies:" in user_load_content
    assert "profile:" in user_load_content


def test_user_policies_nested_type(user_load_content):
    """policies field should reference PolicyLoadOptions since Policy has relationships."""
    assert "PolicyLoadOptions" in user_load_content


# ------------------------------------------------------------------
# Claim load options (leaf)
# ------------------------------------------------------------------

def test_claim_load_options_leaf(claim_load_content):
    """Claim.policy should be LoadStrategy | None since Policy has relationships,
    but Claim itself is a leaf. Check that the policy field exists."""
    # Claim has a policy relationship. Policy has relationships (holder, claims),
    # so it should get PolicyLoadOptions nesting.
    assert "policy:" in claim_load_content


# ------------------------------------------------------------------
# Category (self-referential)
# ------------------------------------------------------------------

def test_category_self_referential(category_load_content):
    """Category load options should handle self-referential relationships."""
    assert "class CategoryLoadOptions" in category_load_content
    assert "parent:" in category_load_content or "children:" in category_load_content


# ------------------------------------------------------------------
# LoadStrategy enum
# ------------------------------------------------------------------

def test_load_strategy_enum(user_load_content):
    """LoadStrategy enum should have SELECT_IN, JOINED, SUBQUERY."""
    assert "class LoadStrategy" in user_load_content
    assert "SELECT_IN" in user_load_content
    assert "JOINED" in user_load_content
    assert "SUBQUERY" in user_load_content
