"""Tests for load options generation.

These tests compile and import generated load option modules, then verify
class structure and LoadStrategy enum through actual inspection.
"""
from __future__ import annotations

import py_compile
from dataclasses import fields as dc_fields
from enum import Enum

import pytest


# ---------------------------------------------------------------------------
# Syntax / compile checks
# ---------------------------------------------------------------------------


def test_user_load_options_compile(generated_package):
    """user_load_options.py has no syntax errors."""
    path = generated_package / "user_load_options.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


def test_category_load_options_compile(generated_package):
    """category_load_options.py (self-referential) has no syntax errors."""
    path = generated_package / "category_load_options.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


def test_claim_load_options_compile(generated_package):
    """claim_load_options.py has no syntax errors."""
    path = generated_package / "claim_load_options.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------


def test_user_load_options_importable(gen_import):
    """user_load_options module has UserLoadOptions and LoadStrategy."""
    mod = gen_import("user_load_options")
    assert hasattr(mod, "UserLoadOptions")
    assert hasattr(mod, "LoadStrategy")


def test_load_strategy_enum_values(gen_import):
    """LoadStrategy enum has SELECT_IN, JOINED, SUBQUERY members."""
    LoadStrategy = gen_import("user_load_options").LoadStrategy
    assert issubclass(LoadStrategy, Enum)
    assert hasattr(LoadStrategy, "SELECT_IN")
    assert hasattr(LoadStrategy, "JOINED")
    assert hasattr(LoadStrategy, "SUBQUERY")


# ---------------------------------------------------------------------------
# UserLoadOptions fields
# ---------------------------------------------------------------------------


def test_user_load_options_has_relationship_fields(gen_import):
    """UserLoadOptions has fields for policies and profile relationships."""
    ULO = gen_import("user_load_options").UserLoadOptions
    field_names = {f.name for f in dc_fields(ULO)}
    assert "policies" in field_names
    assert "profile" in field_names


def test_user_load_options_instantiation(gen_import):
    """UserLoadOptions can be instantiated with a LoadStrategy."""
    mod = gen_import("user_load_options")
    opts = mod.UserLoadOptions(policies=mod.LoadStrategy.SELECT_IN)
    assert opts.policies == mod.LoadStrategy.SELECT_IN


# ---------------------------------------------------------------------------
# Claim load options (leaf relationships)
# ---------------------------------------------------------------------------


def test_claim_load_options_has_policy(gen_import):
    """ClaimLoadOptions has a policy field."""
    CLO = gen_import("claim_load_options").ClaimLoadOptions
    field_names = {f.name for f in dc_fields(CLO)}
    assert "policy" in field_names


# ---------------------------------------------------------------------------
# Category self-referential
# ---------------------------------------------------------------------------


def test_category_self_referential_fields(gen_import):
    """CategoryLoadOptions has parent and children fields referencing itself."""
    mod = gen_import("category_load_options")
    CLO = mod.CategoryLoadOptions
    field_names = {f.name for f in dc_fields(CLO)}
    assert "parent" in field_names
    assert "children" in field_names


def test_category_self_referential_instantiation(gen_import):
    """CategoryLoadOptions can nest itself (self-referential)."""
    mod = gen_import("category_load_options")
    # Nested: load children, and for each child, also load its children
    opts = mod.CategoryLoadOptions(
        children=mod.CategoryLoadOptions(children=mod.LoadStrategy.SELECT_IN)
    )
    assert opts.children is not None
