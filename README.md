# RepoDB

Type-safe SQLAlchemy repository generator CLI. Reads SQLAlchemy 2.0+ model definitions and generates fully type-safe repository layers, DTOs, filter classes, and relationship loading options.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
repodb generate --models path/to/models.py --output path/to/output/
```

### Options

- `--models`: Path to a single `.py` file or a directory containing SQLAlchemy model files
- `--output`: Directory where generated code will be written

## Generated Output Structure

```
output/
├── __init__.py              # Re-exports all repositories
├── base.py                  # BaseRepository, filter classes, LoadStrategy
├── user/
│   ├── __init__.py
│   ├── dto.py               # UserCreate, UserUpdate
│   ├── filters.py           # UserFilter
│   ├── load_options.py      # UserLoadOptions
│   └── repository.py        # UserRepository
├── policy/
│   ├── __init__.py
│   ├── dto.py
│   ├── filters.py
│   ├── load_options.py
│   └── repository.py
└── ...
```

## Features

### DTOs (Create & Update)

- `{Model}Create` — includes all non-auto, non-system columns; defaults/nullable fields are optional
- `{Model}Update` — PK fields required, all others optional; uses `exclude_unset` for partial updates

### Type-Safe Filters

Each column gets a filter with type-appropriate operators:

| Type | Operators |
|------|-----------|
| `str` | `eq`, `neq`, `like`, `ilike`, `in_`, `not_in` |
| `int`, `float`, `Decimal` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in_`, `not_in` |
| `bool` | `eq` |
| `datetime`, `date` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte` |
| `Enum` | `eq`, `neq`, `in_`, `not_in` |
| `UUID` | `eq`, `neq`, `in_`, `not_in` |

### Relationship Loading Options

Declare which relationships to eager-load with smart defaults:

```python
# Load user with policies and their claims
user = await repo.get_by_id(
    user_id,
    load_options=UserLoadOptions(
        policies=PolicyLoadOptions(claims=True)
    ),
)
```

Strategies: `SELECT_IN` (default for to-many), `JOINED` (default for to-one), `SUBQUERY`.

### Repository Methods

- `get_by_id(pk, load_options?, include_deleted?)` — single record lookup
- `get_many(filters?, load_options?, order_by?, limit?, offset?, include_deleted?)` — filtered list
- `create(dto)` / `create_many(dtos)` — insert operations
- `update(dto)` — partial update using `exclude_unset`
- `delete(pk)` — hard delete
- `soft_delete(pk)` / `restore(pk)` — soft delete lifecycle (auto-detected via `deleted_at` column)
- `count(filters?, include_deleted?)` — filtered count

### Supported Patterns

- Single and composite primary keys
- Soft delete (`deleted_at` column auto-detection)
- Single-table inheritance (discriminator detection)
- Association/junction tables (auto-skipped)
- Enum columns with constrained filters
- Async sessions (`AsyncSession`) with dependency injection

## Requirements

- Python 3.11+
- SQLAlchemy 2.0+ (Mapped/mapped_column style)
- Pydantic 2.0+
- AsyncSession-based workflows

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
