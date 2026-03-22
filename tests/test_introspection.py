"""Tests for the model introspection engine."""

from __future__ import annotations

from pathlib import Path

from repodb.introspection.engine import introspect_models
from repodb.introspection.ir import RelationshipDirection


SAMPLE_MODELS = Path(__file__).parent / "sample_models.py"


def test_introspect_finds_all_models():
    """Test that introspection finds all model classes."""
    models = introspect_models(SAMPLE_MODELS)
    names = {m.class_name for m in models}
    assert "User" in names
    assert "Policy" in names
    assert "Claim" in names
    assert "Profile" in names
    assert "Tag" in names
    assert "PolicyRider" in names
    assert "Notification" in names
    assert "EmailNotification" in names
    assert "SMSNotification" in names


def test_user_columns():
    """Test User model column extraction."""
    models = introspect_models(SAMPLE_MODELS)
    user = next(m for m in models if m.class_name == "User")

    col_names = {c.name for c in user.columns}
    assert "id" in col_names
    assert "username" in col_names
    assert "email" in col_names
    assert "status" in col_names
    assert "deleted_at" in col_names

    id_col = next(c for c in user.columns if c.name == "id")
    assert id_col.is_primary_key
    assert id_col.is_autoincrement
    assert id_col.python_type == "int"


def test_user_soft_deletable():
    """Test soft delete detection."""
    models = introspect_models(SAMPLE_MODELS)
    user = next(m for m in models if m.class_name == "User")
    assert user.is_soft_deletable

    tag = next(m for m in models if m.class_name == "Tag")
    assert not tag.is_soft_deletable


def test_enum_detection():
    """Test enum column detection."""
    models = introspect_models(SAMPLE_MODELS)
    user = next(m for m in models if m.class_name == "User")

    status_col = next(c for c in user.columns if c.name == "status")
    assert status_col.is_enum
    assert status_col.enum_class_name == "UserStatus"


def test_relationships():
    """Test relationship extraction."""
    models = introspect_models(SAMPLE_MODELS)
    user = next(m for m in models if m.class_name == "User")

    rel_names = {r.attribute_name for r in user.relationships}
    assert "policies" in rel_names
    assert "profile" in rel_names

    policies_rel = next(r for r in user.relationships if r.attribute_name == "policies")
    assert policies_rel.direction == RelationshipDirection.ONE_TO_MANY
    assert policies_rel.related_model_name == "Policy"


def test_composite_pk():
    """Test composite primary key detection."""
    models = introspect_models(SAMPLE_MODELS)
    rider = next(m for m in models if m.class_name == "PolicyRider")

    assert rider.has_composite_pk
    assert len(rider.primary_key_columns) == 2
    assert "policy_id" in rider.primary_key_columns
    assert "rider_id" in rider.primary_key_columns


def test_foreign_key():
    """Test foreign key detection."""
    models = introspect_models(SAMPLE_MODELS)
    policy = next(m for m in models if m.class_name == "Policy")

    user_id_col = next(c for c in policy.columns if c.name == "user_id")
    assert user_id_col.is_foreign_key
    assert user_id_col.foreign_key_target == "users.id"


def test_inheritance():
    """Test single-table inheritance detection."""
    models = introspect_models(SAMPLE_MODELS)

    notif = next(m for m in models if m.class_name == "Notification")
    assert notif.inheritance is not None
    assert notif.inheritance.is_base

    email_notif = next(m for m in models if m.class_name == "EmailNotification")
    assert email_notif.inheritance is not None
    assert email_notif.inheritance.is_child
    assert email_notif.inheritance.discriminator_value == "email"
