"""Tests for code generators.

Verifies that generated Python source code is syntactically valid, contains the
expected classes, and can be compiled. The CLI end-to-end test
(test_cli.py::test_generate_output_is_valid_python) also validates this, but
these tests focus on individual generator outputs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from click.testing import CliRunner

from repodb.cli import main
from repodb.introspection.engine import introspect_models
from repodb.generators.dto import generate_dto
from repodb.generators.filters import generate_filters
from repodb.generators.load_options import generate_load_options
from repodb.generators.repository import generate_repository


SAMPLE_MODELS = Path(__file__).parent / "sample_models.py"


def _get_models():
    return introspect_models(SAMPLE_MODELS)


# ---------------------------------------------------------------------------
# Unit-level: generated source contains expected structures
# ---------------------------------------------------------------------------


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
    # Both PK columns required in Update
    update_section = code.split("class PolicyRiderUpdate")[1]
    assert "policy_id: int\n" in update_section or "policy_id: int" in update_section
    assert "rider_id: int\n" in update_section or "rider_id: int" in update_section


def test_filter_generation():
    """Test filter generation."""
    models = _get_models()
    policy = next(m for m in models if m.class_name == "Policy")
    code = generate_filters(policy)

    assert "class PolicyFilter(BaseModel):" in code
    assert "name: StringFilter | None = None" in code
    assert "premium: NumericFilter | None = None" in code
    assert "PolicyStatusFilter" in code


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
    """Test repository generation for composite PK includes PK model."""
    models = _get_models()
    rider = next(m for m in models if m.class_name == "PolicyRider")
    code = generate_repository(rider)

    assert "class PolicyRiderPK(BaseModel):" in code
    assert "policy_id: int" in code
    assert "rider_id: int" in code
    # Verify BaseModel import is present (was a bug before)
    assert "from pydantic import BaseModel" in code


# ---------------------------------------------------------------------------
# End-to-end: CLI generates importable, compilable Python
# ---------------------------------------------------------------------------


def test_all_generated_files_compile():
    """Every .py file produced by the CLI must be valid Python syntax."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(
            main,
            ["generate", "--models", str(SAMPLE_MODELS), "--output", tmpdir],
        )
        assert result.exit_code == 0

        output = Path(tmpdir)
        for py_file in output.rglob("*.py"):
            content = py_file.read_text()
            try:
                compile(content, str(py_file), "exec")
            except SyntaxError as e:
                raise AssertionError(f"Syntax error in {py_file}: {e}")


def test_generated_directory_structure():
    """CLI must produce the expected directory layout."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(
            main,
            ["generate", "--models", str(SAMPLE_MODELS), "--output", tmpdir],
        )
        assert result.exit_code == 0

        output = Path(tmpdir)
        # Top-level files
        assert (output / "base.py").exists()
        assert (output / "__init__.py").exists()

        # Per-model packages
        for model_name in ["user", "policy", "claim", "profile", "tag", "policy_rider"]:
            pkg = output / model_name
            assert pkg.is_dir(), f"Missing package: {model_name}"
            for fname in ["__init__.py", "dto.py", "filters.py", "load_options.py", "repository.py"]:
                assert (pkg / fname).exists(), f"Missing {model_name}/{fname}"


def test_non_soft_deletable_flag():
    """Tag has no deleted_at → soft_deletable must be False."""
    models = _get_models()
    tag = next(m for m in models if m.class_name == "Tag")
    code = generate_repository(tag)
    assert "soft_deletable = False" in code


def test_soft_deletable_flag():
    """User has deleted_at → soft_deletable must be True."""
    models = _get_models()
    user = next(m for m in models if m.class_name == "User")
    code = generate_repository(user)
    assert "soft_deletable = True" in code
