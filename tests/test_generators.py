"""Tests for code generators."""

from __future__ import annotations

from pathlib import Path

from repodb.introspection.engine import introspect_models
from repodb.generators.dto import generate_dto
from repodb.generators.filters import generate_filters
from repodb.generators.load_options import generate_load_options
from repodb.generators.repository import generate_repository


SAMPLE_MODELS = Path(__file__).parent / "sample_models.py"


def _get_models():
    return introspect_models(SAMPLE_MODELS)


def test_dto_generation():
    """Test DTO generation for User model."""
    models = _get_models()
    user = next(m for m in models if m.class_name == "User")
    code = generate_dto(user)

    assert "class UserCreate(BaseModel):" in code
    assert "class UserUpdate(BaseModel):" in code
    # id should not be in Create (autoincrement)
    assert "    id:" not in code.split("class UserUpdate")[0]
    # deleted_at should not be in either
    assert "deleted_at" not in code
    # status has default, so optional in Create
    assert "status: UserStatus | None = None" in code


def test_dto_composite_pk():
    """Test DTO for composite PK model."""
    models = _get_models()
    rider = next(m for m in models if m.class_name == "PolicyRider")
    code = generate_dto(rider)

    assert "class PolicyRiderCreate(BaseModel):" in code
    assert "class PolicyRiderUpdate(BaseModel):" in code


def test_filter_generation():
    """Test filter generation."""
    models = _get_models()
    policy = next(m for m in models if m.class_name == "Policy")
    code = generate_filters(policy)

    assert "class PolicyFilter(BaseModel):" in code
    assert "name: StringFilter | None = None" in code
    assert "premium: NumericFilter | None = None" in code
    assert "PolicyStatusFilter" in code or "PolicyStatus" in code


def test_load_options_generation():
    """Test load options generation."""
    models = _get_models()
    user = next(m for m in models if m.class_name == "User")
    code = generate_load_options(user, models)

    assert "class UserLoadOptions(BaseModel):" in code
    assert "policies:" in code
    assert "LoadStrategy" in code


def test_repository_generation():
    """Test repository generation."""
    models = _get_models()
    policy = next(m for m in models if m.class_name == "Policy")
    code = generate_repository(policy)

    assert "class PolicyRepository(BaseRepository[" in code
    assert "soft_deletable = True" in code


def test_composite_pk_repository():
    """Test repository generation for composite PK."""
    models = _get_models()
    rider = next(m for m in models if m.class_name == "PolicyRider")
    code = generate_repository(rider)

    assert "class PolicyRiderPK(BaseModel):" in code
    assert "policy_id: int" in code
    assert "rider_id: int" in code
