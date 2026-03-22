# RepoGen

Type-safe SQLAlchemy repository code generator.

RepoGen reads SQLAlchemy 2.0+ model definitions and generates fully type-safe, per-model repositories, DTOs, filter classes, and relationship loading options. The generated code is static `.py` files that type checkers (Pyright/Mypy) can fully validate.

## Requirements

- Python 3.11+
- SQLAlchemy 2.0+ with `Mapped` / `mapped_column` style models
- A `DeclarativeBase` subclass

## Installation

```bash
pip install -e .
```

For development (includes pytest, black, isort, pyright):

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Define your models

```python
# app/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(back_populates="author")

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))

    author: Mapped[User] = relationship(back_populates="posts")
```

### 2. Generate repository code

```bash
repogen generate --models app/models.py --output app/generated
```

This produces:

```
app/generated/
├── __init__.py
├── _internals/
│   ├── __init__.py
│   ├── filter_utils.py
│   ├── loading_utils.py
│   └── soft_delete.py
├── user_dtos.py
├── user_filters.py
├── user_load_options.py
├── user_repository.py
├── post_dtos.py
├── post_filters.py
├── post_load_options.py
└── post_repository.py
```

### 3. Use the generated code

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.generated import (
    UserRepository, UserCreate, UserUpdate, UserFilter,
    UserLoadOptions, PostLoadOptions,
)
from app.generated.user_filters import StringFilter, BoolFilter
from app.generated.user_load_options import LoadStrategy

async def example(session: AsyncSession):
    async with session.begin():
        repo = UserRepository(session)

        # Create
        user = await repo.create(UserCreate(name="Alice", email="alice@example.com"))

        # Get by ID (soft-delete aware)
        user = await repo.get_by_id(user.id)

        # Get by unique column (auto-generated)
        user = await repo.get_by_email("alice@example.com")

        # Filter
        active_users = await repo.get_many(
            filters=UserFilter(
                is_active=BoolFilter(eq=True),
                name=StringFilter(like="A%"),
            ),
            limit=10,
            order_by=["name"],
        )

        # Eager loading
        users_with_posts = await repo.get_many(
            load_options=UserLoadOptions(posts=LoadStrategy.SELECT_IN),
        )

        # Update
        updated = await repo.update(UserUpdate(id=user.id, name="Alice Smith"))

        # Soft delete / restore
        await repo.delete(user.id)                              # sets deleted_at
        await repo.get_by_id(user.id)                           # returns None
        await repo.get_by_id(user.id, include_deleted=True)     # returns the user
        await repo.restore(user.id)                             # clears deleted_at

        # Hard delete
        await repo.hard_delete(user.id)

        # Count / exists
        count = await repo.count(filters=UserFilter(is_active=BoolFilter(eq=True)))
        exists = await repo.exists(filters=UserFilter(name=StringFilter(eq="Alice")))
```

## CLI Reference

```
repogen generate [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--models` | Path to models file or directory | *required* |
| `--output` | Output directory for generated code | `./generated` |
| `--config` | Path to `repogen.toml` config file | auto-detected |
| `--dry-run` | Print what would be generated without writing | off |
| `--verbose` | Print detailed introspection info | off |

You can also run it as a module:

```bash
python -m repogen generate --models app/models.py --output app/generated
```

## Configuration

Create a `repogen.toml` file in your project root (or pass `--config path/to/config.toml`):

```toml
[repogen]
soft_delete_column = "deleted_at"       # Column name that triggers soft-delete detection
generate_hard_delete = true             # Generate hard_delete() on soft-deletable repos
generate_unique_lookups = true          # Auto-generate get_by_<unique_col>() methods
generate_restore = true                 # Generate restore() on soft-deletable repos

[repogen.defaults]
to_one_strategy = "joined"             # Default load strategy for to-one relationships
to_many_strategy = "selectin"          # Default load strategy for to-many relationships

[repogen.exclude]
models = ["Base", "AbstractBase"]       # Model class names to skip
columns = ["created_at", "updated_at"]  # Columns to exclude from UpdateDTO
```

All settings are optional and have sensible defaults.

## What Gets Generated

For each model, RepoGen generates four files:

### DTOs (`<model>_dtos.py`)

- **`ModelCreate`** -- Fields for creating a record. Autoincrement PKs and the soft-delete column are excluded. Nullable fields and fields with defaults are optional.
- **`ModelUpdate`** -- PK fields are required (to locate the record). All other fields are `type | None = None` (only set fields are applied).

### Filters (`<model>_filters.py`)

Type-safe filter classes with operators matched to column types:

| Python Type | Operators |
|---|---|
| `str` | `eq`, `neq`, `like`, `ilike`, `in_`, `not_in`, `is_null` |
| `int`, `float`, `Decimal` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in_`, `not_in`, `is_null` |
| `bool` | `eq`, `is_null` |
| `UUID` | `eq`, `neq`, `in_`, `not_in`, `is_null` |
| `datetime`, `date` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between`, `is_null` |
| `Enum` | `eq`, `neq`, `in_`, `not_in`, `is_null` |

Filters support `and_` / `or_` for combining conditions.

### Load Options (`<model>_load_options.py`)

Dataclass for declaring which relationships to eager-load and how:

```python
UserLoadOptions(
    posts=LoadStrategy.SELECT_IN,                    # simple
    posts=PostLoadOptions(comments=LoadStrategy.JOINED),  # nested
)
```

Strategies: `SELECT_IN`, `JOINED`, `SUBQUERY`.

### Repository (`<model>_repository.py`)

Every repository has these methods:

| Method | Description |
|---|---|
| `get_by_id(pk, ...)` | Fetch by primary key |
| `get_many(filters, load_options, order_by, limit, offset)` | Query with filters |
| `get_one(filters, ...)` | Fetch single match |
| `create(dto)` | Create from DTO |
| `create_many(dtos)` | Bulk create |
| `update(dto)` | Partial update |
| `delete(pk)` | Delete (soft or hard depending on model) |
| `count(filters)` | Count matching records |
| `exists(filters)` | Check if any match |

Soft-deletable models additionally get:

| Method | Description |
|---|---|
| `hard_delete(pk)` | Permanently remove |
| `restore(pk)` | Clear `deleted_at` |

All read methods accept `include_deleted: bool = False`.

Models with `unique=True` columns get auto-generated `get_by_<column>()` methods.

Composite primary keys are fully supported -- `get_by_id`, `update`, and `delete` accept each PK column as a separate parameter.

## Key Design Decisions

- **No generic base repository.** Every generated class has fully resolved, concrete types. `UserRepository.get_by_id()` takes `id: int`, not `id: Any`.
- **Async-first.** All repositories use `AsyncSession`. No sync support.
- **Repositories don't own sessions.** The caller controls the session and transaction lifecycle. Repositories never commit or create sessions.
- **Soft delete is structural.** Models with a `deleted_at` column get fundamentally different generated code, not runtime branching.
- **Generated files are re-generation safe.** Files with the `AUTO-GENERATED by RepoGen` header are overwritten; files without it are skipped with a warning.

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

The test suite includes:
- Unit tests for introspection, DTO generation, filter generation, load options, and repository generation
- End-to-end integration tests that generate code and run it against an in-memory SQLite database
