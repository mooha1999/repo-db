"""Tests for filter generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR
from repogen.generators.filter_generator import generate_filters

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
def user_filter_content(model_irs: list[ModelIR], tmp_path: Path) -> str:
    user = _get_model(model_irs, "User")
    generate_filters(user, tmp_path)
    return (tmp_path / "user_filters.py").read_text()


# ---- Filter fields ----------------------------------------------------------


def test_user_filter_fields(user_filter_content: str):
    """All filterable columns are present in UserFilter."""
    filter_block = user_filter_content.split("class UserFilter")[1]
    for field in ("id", "name", "email", "role", "is_active", "created_at"):
        assert f"{field}:" in filter_block, f"{field} should be in UserFilter"


def test_user_filter_excludes_soft_delete(user_filter_content: str):
    """deleted_at is not present in the filter class."""
    filter_block = user_filter_content.split("class UserFilter")[1]
    field_lines = [
        line.strip()
        for line in filter_block.splitlines()
        if ":" in line
        and not line.strip().startswith("#")
        and not line.strip().startswith('"""')
    ]
    field_names = [line.split(":")[0].strip() for line in field_lines]
    assert "deleted_at" not in field_names


# ---- Enum filter ------------------------------------------------------------


def test_enum_filter_generated(user_filter_content: str):
    """UserRoleFilter class is generated for the UserRole enum."""
    assert "class UserRoleFilter" in user_filter_content


# ---- Built-in filter classes ------------------------------------------------


def test_string_filter_class(user_filter_content: str):
    """StringFilter has eq, neq, like, ilike, in_, not_in, is_null."""
    sf_block = user_filter_content.split("class StringFilter")[1].split("class ")[0]
    for field in ("eq:", "neq:", "like:", "ilike:", "in_:", "not_in:", "is_null:"):
        assert field in sf_block, f"StringFilter should have {field}"


def test_int_filter_class(user_filter_content: str):
    """IntFilter has eq, neq, gt, gte, lt, lte, in_, not_in."""
    if_block = user_filter_content.split("class IntFilter")[1].split("class ")[0]
    for field in ("eq:", "neq:", "gt:", "gte:", "lt:", "lte:", "in_:", "not_in:"):
        assert field in if_block, f"IntFilter should have {field}"


def test_bool_filter_class(user_filter_content: str):
    """BoolFilter has eq, is_null."""
    bf_block = user_filter_content.split("class BoolFilter")[1].split("class ")[0]
    assert "eq:" in bf_block
    assert "is_null:" in bf_block


def test_datetime_filter_class(user_filter_content: str):
    """DateTimeFilter has between."""
    dt_block = user_filter_content.split("class DateTimeFilter")[1].split("class ")[0]
    assert "between:" in dt_block


# ---- Logical operators ------------------------------------------------------


def test_and_or_fields(user_filter_content: str):
    """and_ and or_ fields are present on the main UserFilter."""
    filter_block = user_filter_content.split("class UserFilter")[1]
    assert "and_:" in filter_block
    assert "or_:" in filter_block
