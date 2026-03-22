"""Tests for the CLI."""

from __future__ import annotations

import tempfile
from pathlib import Path

from click.testing import CliRunner

from repodb.cli import main


SAMPLE_MODELS = Path(__file__).parent / "sample_models.py"


def test_generate_command():
    """Test the generate CLI command."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["generate", "--models", str(SAMPLE_MODELS), "--output", tmpdir])
        assert result.exit_code == 0
        assert "Found" in result.output
        assert "Done!" in result.output


def test_generate_creates_files():
    """Test that generate creates expected files."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["generate", "--models", str(SAMPLE_MODELS), "--output", tmpdir])
        assert result.exit_code == 0

        output = Path(tmpdir)
        assert (output / "base.py").exists()
        assert (output / "__init__.py").exists()
        assert (output / "user" / "dto.py").exists()
        assert (output / "user" / "filters.py").exists()
        assert (output / "user" / "load_options.py").exists()
        assert (output / "user" / "repository.py").exists()
        assert (output / "policy" / "repository.py").exists()


def test_generate_output_is_valid_python():
    """Test that generated files are valid Python."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["generate", "--models", str(SAMPLE_MODELS), "--output", tmpdir])
        assert result.exit_code == 0

        output = Path(tmpdir)
        for py_file in output.rglob("*.py"):
            content = py_file.read_text()
            try:
                compile(content, str(py_file), "exec")
            except SyntaxError as e:
                raise AssertionError(f"Syntax error in {py_file}: {e}")
