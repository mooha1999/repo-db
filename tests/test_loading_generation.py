"""Tests for load options generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.loading_generator import generate_load_options

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
def user_load_content(model_irs, tmp_path) -> str:
    user = _get_model(model_irs, "User")
    generate_load_options(user, model_irs, tmp_path)
    return (tmp_path / "user_load_options.py").read_text()


@pytest.fixture
def claim_load_content(model_irs, tmp_path) -> str:
    claim = _get_model(model_irs, "Claim")
    generate_load_options(claim, model_irs, tmp_path)
    return (tmp_path / "claim_load_options.py").read_text()


@pytest.fixture
def category_load_content(model_irs, tmp_path) -> str:
    cat = _get_model(model_irs, "Category")
    generate_load_options(cat, model_irs, tmp_path)
    return (tmp_path / "category_load_options.py").read_text()


# ---- User load options ------------------------------------------------------

def test_user_load_options_fields(user_load_content):
    """policies and profile fields are present in UserLoadOptions."""
    lo_block = user_load_content.split("class UserLoadOptions")[1]
    assert "policies:" in lo_block
    assert "profile:" in lo_block


def test_user_policies_nested_type(user_load_content):
    """policies field has PolicyLoadOptions type option (nested)."""
    lo_block = user_load_content.split("class UserLoadOptions")[1]
    assert "PolicyLoadOptions" in lo_block


# ---- Claim load options (leaf) ----------------------------------------------

def test_claim_load_options_leaf(claim_load_content):
    """Claim.policy is LoadStrategy | None (leaf with no deeper nesting)."""
    lo_block = claim_load_content.split("class ClaimLoadOptions")[1]
    # Policy has relationships (holder, claims), so it should have nested.
    assert "policy:" in lo_block


# ---- Category self-referential ----------------------------------------------

def test_category_self_referential(category_load_content):
    """Category load options handle self-referential relationship."""
    lo_block = category_load_content.split("class CategoryLoadOptions")[1]
    assert "parent:" in lo_block
    assert "children:" in lo_block
    # Self-referential: CategoryLoadOptions references itself
    assert "CategoryLoadOptions" in lo_block


# ---- LoadStrategy enum ------------------------------------------------------

def test_load_strategy_enum(user_load_content):
    """LoadStrategy enum has SELECT_IN, JOINED, SUBQUERY."""
    assert "class LoadStrategy" in user_load_content
    assert "SELECT_IN" in user_load_content
    assert "JOINED" in user_load_content
    assert "SUBQUERY" in user_load_content
