"""RepoDB CLI interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="repodb")
def main() -> None:
    """RepoDB: Type-safe SQLAlchemy repository generator."""
    pass


@main.command()
@click.option(
    "--models",
    required=True,
    type=click.Path(exists=True),
    help="Path to models file or directory containing model files.",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output directory for generated code.",
)
def generate(models: str, output: str) -> None:
    """Generate repository layer from SQLAlchemy models."""
    from .introspection.engine import introspect_models
    from .generators.orchestrator import generate_all

    models_path = Path(models).resolve()
    output_path = Path(output).resolve()

    click.echo(f"Introspecting models from: {models_path}")

    try:
        model_irs = introspect_models(models_path)
    except Exception as e:
        click.echo(f"Error introspecting models: {e}", err=True)
        sys.exit(1)

    if not model_irs:
        click.echo("No models found. Check that your models inherit from DeclarativeBase.")
        sys.exit(1)

    click.echo(f"Found {len(model_irs)} model(s):")
    for ir in model_irs:
        suffix = ""
        if ir.is_association_table:
            suffix = " (association table - skipped)"
        elif ir.is_soft_deletable:
            suffix = " (soft-deletable)"
        click.echo(f"  - {ir.class_name} ({ir.table_name}){suffix}")

    click.echo(f"\nGenerating to: {output_path}")
    stats = generate_all(model_irs, output_path)

    click.echo(f"\nDone!")
    click.echo(f"  Models found: {stats['models_found']}")
    click.echo(f"  Repositories generated: {stats['models_generated']}")
    if stats['skipped_association_tables'] > 0:
        click.echo(f"  Skipped association tables: {stats['skipped_association_tables']}")


if __name__ == "__main__":
    main()
