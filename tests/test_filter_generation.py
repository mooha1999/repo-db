"""Tests for filter generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.filter_generator import generate_filters

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
def user_filter_content(all_models, tmp_path):
    user = _find_model(all_models, "User")
    generate_filters(user, tmp_path)
    return (tmp_path / "user_filters.py").read_text()


# ------------------------------------------------------------------
# User filter fields
# ------------------------------------------------------------------

def test_user_filter_fields(user_filter_content):
    """All filterable columns should be present in UserFilter."""
    # Extract UserFilter class body
    filter_start = user_filter_content.index("class UserFilter")
    filter_body = user_filter_content[filter_start:]

    for col in ("id", "name", "email", "role", "is_active", "created_at"):
        assert f"{col}:" in filter_body, f"{col} should be a filter field"


def test_user_filter_excludes_soft_delete(user_filter_content):
    """deleted_at should not appear in UserFilter fields."""
    filter_start = user_filter_content.index("class UserFilter")
    filter_body = user_filter_content[filter_start:]
    lines = filter_body.split("\n")
    field_lines = [l.strip() for l in lines if ":" in l and not l.strip().startswith("class") and not l.strip().startswith("#") and not l.strip().startswith('"""')]
    field_names = [l.split(":")[0].strip() for l in field_lines]
    assert "deleted_at" not in field_names


# ------------------------------------------------------------------
# Enum filter
# ------------------------------------------------------------------

def test_enum_filter_generated(user_filter_content):
    """A UserRoleFilter class should be generated for the enum column."""
    assert "class UserRoleFilter" in user_filter_content


# ------------------------------------------------------------------
# Base filter classes
# ------------------------------------------------------------------

def test_string_filter_class(user_filter_content):
    """StringFilter should have eq, neq, like, ilike, in_, not_in, is_null."""
    sf_start = user_filter_content.index("class StringFilter")
    # Find the end (next class or end of file)
    next_class = user_filter_content.index("class IntFilter")
    sf_body = user_filter_content[sf_start:next_class]
    for field in ("eq:", "neq:", "like:", "ilike:", "in_:", "not_in:", "is_null:"):
        assert field in sf_body, f"StringFilter missing {field}"


def test_int_filter_class(user_filter_content):
    """IntFilter should have eq, neq, gt, gte, lt, lte, in_, not_in."""
    if_start = user_filter_content.index("class IntFilter")
    next_class = user_filter_content.index("class FloatFilter")
    if_body = user_filter_content[if_start:next_class]
    for field in ("eq:", "neq:", "gt:", "gte:", "lt:", "lte:", "in_:", "not_in:"):
        assert field in if_body, f"IntFilter missing {field}"


def test_bool_filter_class(user_filter_content):
    """BoolFilter should have eq and is_null."""
    bf_start = user_filter_content.index("class BoolFilter")
    next_class = user_filter_content.index("class UUIDFilter")
    bf_body = user_filter_content[bf_start:next_class]
    assert "eq:" in bf_body
    assert "is_null:" in bf_body


def test_datetime_filter_class(user_filter_content):
    """DateTimeFilter should have between."""
    dtf_start = user_filter_content.index("class DateTimeFilter")
    dtf_end = user_filter_content.index("class DateFilter")
    dtf_body = user_filter_content[dtf_start:dtf_end]
    assert "between:" in dtf_body


# ------------------------------------------------------------------
# Logical operators
# ------------------------------------------------------------------

def test_and_or_fields(user_filter_content):
    """UserFilter should have and_ and or_ fields."""
    filter_start = user_filter_content.index("class UserFilter")
    filter_body = user_filter_content[filter_start:]
    assert "and_:" in filter_body
    assert "or_:" in filter_body
