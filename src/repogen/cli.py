"""RepoGen CLI — Type-Safe SQLAlchemy Repository Code Generator."""
from __future__ import annotations

import sys
from pathlib import Path

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="repogen")
def main():
    """RepoGen — Type-Safe SQLAlchemy Repository Code Generator."""
    pass


@main.command()
@click.option("--models", required=True, type=click.Path(exists=True), help="Path to models file or directory")
@click.option("--output", default="./generated", type=click.Path(), help="Output directory for generated code")
@click.option("--config", default=None, type=click.Path(exists=True), help="Path to repogen.toml config file")
@click.option("--dry-run", is_flag=True, default=False, help="Print what would be generated without writing")
@click.option("--verbose", is_flag=True, default=False, help="Print detailed introspection info")
def generate(models: str, output: str, config: str | None, dry_run: bool, verbose: bool):
    """Generate repository code from SQLAlchemy models."""
    import tomli
    from repogen.introspection.engine import discover_models
    from repogen.generators.dto_generator import generate_dtos
    from repogen.generators.filter_generator import generate_filters
    from repogen.generators.loading_generator import generate_load_options
    from repogen.generators.repo_generator import generate_repository
    from repogen.generators.internals_generator import generate_internals

    # Load config
    cfg = _load_config(config)

    soft_delete_column = cfg.get("soft_delete_column", "deleted_at")
    exclude_models = cfg.get("exclude", {}).get("models", ["Base", "AbstractBase"])
    exclude_columns = cfg.get("exclude", {}).get("columns", ["created_at", "updated_at"])

    click.echo(f"Discovering models from: {models}")

    # Phase 1: Introspect models
    try:
        model_irs = discover_models(
            models_path=models,
            soft_delete_column=soft_delete_column,
            exclude_models=exclude_models,
        )
    except Exception as e:
        click.echo(f"Error discovering models: {e}", err=True)
        sys.exit(1)

    if not model_irs:
        click.echo("No models found.", err=True)
        sys.exit(1)

    click.echo(f"Found {len(model_irs)} model(s): {', '.join(m.class_name for m in model_irs)}")

    if verbose:
        for m in model_irs:
            click.echo(f"\n  {m.class_name} ({m.table_name}):")
            click.echo(f"    Columns: {', '.join(c.name for c in m.columns)}")
            click.echo(f"    PKs: {', '.join(c.name for c in m.primary_key_columns)}")
            click.echo(f"    Relationships: {', '.join(r.name for r in m.relationships)}")
            click.echo(f"    Soft-deletable: {m.is_soft_deletable}")

    if dry_run:
        click.echo("\n[Dry run] Would generate:")
        for m in model_irs:
            snake = _snake_case(m.class_name)
            click.echo(f"  {output}/{snake}_dtos.py")
            click.echo(f"  {output}/{snake}_filters.py")
            click.echo(f"  {output}/{snake}_load_options.py")
            click.echo(f"  {output}/{snake}_repository.py")
        click.echo(f"  {output}/_internals/filter_utils.py")
        click.echo(f"  {output}/_internals/loading_utils.py")
        click.echo(f"  {output}/_internals/soft_delete.py")
        click.echo(f"  {output}/__init__.py")
        return

    # Create output directory
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Compute internals_path - the Python import path for the generated package
    # This is the package name of the output directory
    internals_path = output_path.name

    repo_config = {
        "generate_hard_delete": cfg.get("generate_hard_delete", True),
        "generate_unique_lookups": cfg.get("generate_unique_lookups", True),
        "generate_restore": cfg.get("generate_restore", True),
        "exclude_columns": exclude_columns,
    }

    # Phase 6: Generate internals first
    click.echo("\nGenerating internal utilities...")
    generate_internals(output_path)

    # Phases 2-5: Generate per-model files
    for model_ir in model_irs:
        click.echo(f"Generating code for {model_ir.class_name}...")
        generate_dtos(model_ir, output_path, exclude_columns=exclude_columns)
        generate_filters(model_ir, output_path)
        generate_load_options(model_ir, model_irs, output_path)
        generate_repository(model_ir, output_path, internals_path=internals_path, config=repo_config)

    # Generate __init__.py that re-exports everything
    _generate_init(model_irs, output_path)

    # Try to format with black and isort
    _try_format(output_path)

    click.echo(f"\nDone! Generated files in: {output_path}")


def _load_config(config_path: str | None) -> dict:
    """Load repogen.toml config file if it exists."""
    if config_path is None:
        # Try default location
        default = Path("repogen.toml")
        if default.exists():
            config_path = str(default)
        else:
            return {}

    try:
        import tomli
        with open(config_path, "rb") as f:
            data = tomli.load(f)
        return data.get("repogen", {})
    except ImportError:
        # Python 3.11+ has tomllib
        try:
            import tomllib
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            return data.get("repogen", {})
        except ImportError:
            click.echo("Warning: Cannot read config file (tomli/tomllib not available)", err=True)
            return {}


def _snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    import re
    s = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', name)
    s = re.sub(r'(?<=[A-Z])([A-Z][a-z])', r'_\1', s)
    return s.lower()


def _generate_init(model_irs: list, output_path: Path):
    """Generate __init__.py that re-exports all public classes."""
    lines = [
        "# ============================================================",
        "# AUTO-GENERATED by RepoGen — DO NOT EDIT MANUALLY",
        "# Re-run `repogen generate` after modifying models.",
        "# ============================================================",
        "",
    ]

    for m in model_irs:
        snake = _snake_case(m.class_name)
        name = m.class_name
        lines.append(f"from .{snake}_dtos import {name}Create, {name}Update")
        lines.append(f"from .{snake}_filters import {name}Filter")
        lines.append(f"from .{snake}_load_options import {name}LoadOptions")
        lines.append(f"from .{snake}_repository import {name}Repository")

    lines.append("")  # trailing newline

    init_path = output_path / "__init__.py"
    init_path.write_text("\n".join(lines))


def _try_format(output_path: Path):
    """Try to format generated files with black and isort."""
    import subprocess

    try:
        subprocess.run(
            ["black", str(output_path), "--quiet"],
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        subprocess.run(
            ["isort", str(output_path), "--quiet"],
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
