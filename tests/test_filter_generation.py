"""Tests for filter generation.

These tests compile and import generated filter modules, then verify
class structure and field operators through actual Pydantic model inspection.
"""
from __future__ import annotations

import py_compile

import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Syntax / compile checks
# ---------------------------------------------------------------------------


def test_user_filters_compile(generated_package):
    """user_filters.py has no syntax errors."""
    path = generated_package / "user_filters.py"
    assert path.exists(), "user_filters.py was not generated"
    py_compile.compile(str(path), doraise=True)


def test_policy_filters_compile(generated_package):
    """policy_filters.py has no syntax errors."""
    path = generated_package / "policy_filters.py"
    assert path.exists()
    py_compile.compile(str(path), doraise=True)


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------


def test_user_filters_importable(gen_import):
    """user_filters module can be imported and contains expected classes."""
    mod = gen_import("user_filters")
    for cls_name in ("UserFilter", "StringFilter", "IntFilter", "BoolFilter", "DateTimeFilter"):
        assert hasattr(mod, cls_name), f"{cls_name} missing from user_filters"
        assert issubclass(getattr(mod, cls_name), BaseModel)


# ---------------------------------------------------------------------------
# Filter fields on UserFilter
# ---------------------------------------------------------------------------


def test_user_filter_has_expected_fields(gen_import):
    """UserFilter has filter fields for all non-soft-delete columns."""
    UserFilter = gen_import("user_filters").UserFilter
    fields = UserFilter.model_fields
    for col in ("id", "name", "email", "role", "is_active", "created_at"):
        assert col in fields, f"UserFilter missing field: {col}"


def test_user_filter_excludes_soft_delete(gen_import):
    """deleted_at is excluded from UserFilter."""
    UserFilter = gen_import("user_filters").UserFilter
    assert "deleted_at" not in UserFilter.model_fields


def test_user_filter_and_or_fields(gen_import):
    """and_ and or_ logical combinator fields are present."""
    UserFilter = gen_import("user_filters").UserFilter
    assert "and_" in UserFilter.model_fields
    assert "or_" in UserFilter.model_fields


# ---------------------------------------------------------------------------
# Built-in filter class operators
# ---------------------------------------------------------------------------


def test_string_filter_operators(gen_import):
    """StringFilter has eq, neq, like, ilike, in_, not_in, is_null."""
    StringFilter = gen_import("user_filters").StringFilter
    fields = StringFilter.model_fields
    for op in ("eq", "neq", "like", "ilike", "in_", "not_in", "is_null"):
        assert op in fields, f"StringFilter missing operator: {op}"


def test_int_filter_operators(gen_import):
    """IntFilter has eq, neq, gt, gte, lt, lte, in_, not_in, is_null."""
    IntFilter = gen_import("user_filters").IntFilter
    fields = IntFilter.model_fields
    for op in ("eq", "neq", "gt", "gte", "lt", "lte", "in_", "not_in", "is_null"):
        assert op in fields, f"IntFilter missing operator: {op}"


def test_bool_filter_operators(gen_import):
    """BoolFilter has eq and is_null."""
    BoolFilter = gen_import("user_filters").BoolFilter
    fields = BoolFilter.model_fields
    assert "eq" in fields
    assert "is_null" in fields


def test_datetime_filter_has_between(gen_import):
    """DateTimeFilter supports the between operator."""
    DateTimeFilter = gen_import("user_filters").DateTimeFilter
    assert "between" in DateTimeFilter.model_fields


# ---------------------------------------------------------------------------
# Enum filter
# ---------------------------------------------------------------------------


def test_enum_filter_generated(gen_import):
    """UserRoleFilter class is generated for the UserRole enum."""
    mod = gen_import("user_filters")
    assert hasattr(mod, "UserRoleFilter")
    assert issubclass(mod.UserRoleFilter, BaseModel)
    fields = mod.UserRoleFilter.model_fields
    for op in ("eq", "neq", "in_", "not_in", "is_null"):
        assert op in fields, f"UserRoleFilter missing operator: {op}"


# ---------------------------------------------------------------------------
# Instantiation / logic checks
# ---------------------------------------------------------------------------


def test_string_filter_instantiation(gen_import):
    """StringFilter can be instantiated with various operators."""
    StringFilter = gen_import("user_filters").StringFilter
    f = StringFilter(eq="hello")
    assert f.eq == "hello"
    assert f.neq is None

    f2 = StringFilter(like="A%", is_null=False)
    assert f2.like == "A%"
    assert f2.is_null is False


def test_user_filter_nested_instantiation(gen_import):
    """UserFilter can be constructed with nested filter objects."""
    mod = gen_import("user_filters")
    uf = mod.UserFilter(
        name=mod.StringFilter(eq="Alice"),
        is_active=mod.BoolFilter(eq=True),
    )
    assert uf.name is not None
    assert uf.name.eq == "Alice"


def test_user_filter_and_or_instantiation(gen_import):
    """UserFilter supports and_/or_ with lists of sub-filters."""
    mod = gen_import("user_filters")
    combined = mod.UserFilter(
        or_=[
            mod.UserFilter(name=mod.StringFilter(eq="Alice")),
            mod.UserFilter(name=mod.StringFilter(eq="Bob")),
        ]
    )
    assert combined.or_ is not None
    assert len(combined.or_) == 2
