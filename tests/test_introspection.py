"""Tests for the introspection engine."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from repogen.introspection.engine import discover_models
from repogen.introspection.ir import ModelIR

# Path to test models file
_MODELS_FILE = Path(__file__).parent / "test_models" / "models.py"


def _get_model(models: list[ModelIR], class_name: str) -> ModelIR:
    """Find a ModelIR by class_name."""
    for m in models:
        if m.class_name == class_name:
            return m
    raise ValueError(f"Model {class_name!r} not found in {[m.class_name for m in models]}")


def _get_column(model: ModelIR, col_name: str):
    """Find a ColumnIR by name."""
    for c in model.columns:
        if c.name == col_name:
            return c
    raise ValueError(f"Column {col_name!r} not found in {model.class_name}")


@pytest.fixture(scope="module")
def model_irs() -> list[ModelIR]:
    return discover_models(str(_MODELS_FILE))


# ---- Discovery tests -------------------------------------------------------

def test_discover_models_from_file(model_irs):
    """discover_models finds the expected number of models from a single file."""
    names = {m.class_name for m in model_irs}
    assert names >= {"User", "UserProfile", "Policy", "Claim", "Category", "TenantPolicy"}
    assert len(model_irs) >= 6


def test_discover_models_excludes_base(model_irs):
    """Base class is excluded from the discovered models."""
    names = {m.class_name for m in model_irs}
    assert "Base" not in names


# ---- User model IR ---------------------------------------------------------

def test_user_model_ir(model_irs):
    """User ModelIR has expected class_name, table_name, columns, relationships, and soft delete."""
    user = _get_model(model_irs, "User")
    assert user.class_name == "User"
    assert user.table_name == "users"
    assert user.is_soft_deletable is True
    assert user.soft_delete_column == "deleted_at"

    col_names = {c.name for c in user.columns}
    assert col_names >= {"id", "name", "email", "role", "is_active", "bio", "deleted_at", "created_at"}

    rel_names = {r.name for r in user.relationships}
    assert rel_names >= {"policies", "profile"}


# ---- Policy model IR -------------------------------------------------------

def test_policy_model_ir(model_irs):
    """Policy is not soft-deletable and has relationships."""
    policy = _get_model(model_irs, "Policy")
    assert policy.is_soft_deletable is False
    assert policy.soft_delete_column is None

    rel_names = {r.name for r in policy.relationships}
    assert "holder" in rel_names
    assert "claims" in rel_names


# ---- TenantPolicy composite PK ---------------------------------------------

def test_tenant_policy_composite_pk(model_irs):
    """TenantPolicy has a composite primary key with 2 PK columns."""
    tp = _get_model(model_irs, "TenantPolicy")
    assert len(tp.primary_key_columns) == 2
    pk_names = {c.name for c in tp.primary_key_columns}
    assert pk_names == {"tenant_id", "policy_number"}


# ---- Category self-referential ----------------------------------------------

def test_category_self_referential(model_irs):
    """Category has at least one self-referential relationship."""
    cat = _get_model(model_irs, "Category")
    self_refs = [r for r in cat.relationships if r.is_self_referential]
    assert len(self_refs) >= 1


# ---- Column type detection --------------------------------------------------

def test_column_types_detected(model_irs):
    """Python types are correctly mapped for various column types."""
    user = _get_model(model_irs, "User")
    policy = _get_model(model_irs, "Policy")

    assert _get_column(user, "id").python_type is int
    assert _get_column(user, "name").python_type is str
    assert _get_column(user, "is_active").python_type is bool
    assert _get_column(user, "created_at").python_type is datetime
    assert _get_column(policy, "premium").python_type is Decimal


# ---- Enum values ------------------------------------------------------------

def test_enum_values_extracted(model_irs):
    """Enum values are extracted from UserRole enum on User.role."""
    user = _get_model(model_irs, "User")
    role_col = _get_column(user, "role")
    assert role_col.enum_values is not None
    assert set(role_col.enum_values) >= {"admin", "user", "moderator"}


# ---- Unique constraints -----------------------------------------------------

def test_unique_constraints_detected(model_irs):
    """Unique constraints are detected for User.email and Policy.policy_number."""
    user = _get_model(model_irs, "User")
    email_col = _get_column(user, "email")
    assert email_col.is_unique is True

    policy = _get_model(model_irs, "Policy")
    pn_col = _get_column(policy, "policy_number")
    assert pn_col.is_unique is True


# ---- Foreign key detection --------------------------------------------------

def test_foreign_key_detected(model_irs):
    """Foreign key is detected on Policy.holder_id."""
    policy = _get_model(model_irs, "Policy")
    holder_col = _get_column(policy, "holder_id")
    assert holder_col.is_foreign_key is True
    assert holder_col.foreign_key_target is not None
    assert "users.id" in holder_col.foreign_key_target


# ---- Autoincrement detection ------------------------------------------------

def test_autoincrement_detection(model_irs):
    """Autoincrement is detected on integer primary keys."""
    user = _get_model(model_irs, "User")
    id_col = _get_column(user, "id")
    assert id_col.is_autoincrement is True
    assert id_col.is_primary_key is True


# ---- Server default detection -----------------------------------------------

def test_server_default_detected(model_irs):
    """server_default is detected on created_at columns."""
    user = _get_model(model_irs, "User")
    created_col = _get_column(user, "created_at")
    assert created_col.has_server_default is True


# ---- Nullable detection -----------------------------------------------------

def test_nullable_detection(model_irs):
    """Nullable columns are correctly identified."""
    user = _get_model(model_irs, "User")
    bio_col = _get_column(user, "bio")
    assert bio_col.is_nullable is True

    name_col = _get_column(user, "name")
    assert name_col.is_nullable is False
