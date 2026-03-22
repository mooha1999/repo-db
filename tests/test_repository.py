"""Integration tests for the repository layer.

These tests are "honest" end-to-end tests that:
1. Run the repodb CLI to generate repository code from sample_models.py
2. Dynamically import the generated modules
3. Test the generated repositories against a real async SQLite database
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from click.testing import CliRunner
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from repodb.cli import main
from tests.sample_models import (
    Base,
    PolicyStatus,
    UserStatus,
)


SAMPLE_MODELS = Path(__file__).parent / "sample_models.py"


# ---------------------------------------------------------------------------
# Fixture: generate code once, import generated modules
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def generated_package() -> Path:
    """Run the CLI to generate code and return the output directory.

    This fixture runs once per test session. The generated code lives in a
    temporary directory that persists for the entire session.
    """
    tmpdir = tempfile.mkdtemp(prefix="repodb_test_")
    output = Path(tmpdir) / "generated"

    runner = CliRunner()
    result = runner.invoke(
        main, ["generate", "--models", str(SAMPLE_MODELS), "--output", str(output)]
    )
    assert result.exit_code == 0, f"CLI failed:\n{result.output}"

    # Add the parent of the generated package to sys.path so that
    # `import generated` works with all relative imports intact.
    parent_dir = str(output.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Force-import the generated package (and all sub-packages)
    importlib.import_module("generated")

    return output


@pytest.fixture(scope="session")
def gen(generated_package: Path) -> ModuleType:
    """Return the top-level generated package module."""
    return sys.modules["generated"]


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine  # type: ignore[misc]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(async_engine: AsyncEngine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ---------------------------------------------------------------------------
# Helper to grab generated classes by model name
# ---------------------------------------------------------------------------


def _get_classes(model_name: str) -> dict:
    """Return a dict of generated classes for a model."""
    snake = _to_snake(model_name)
    pkg = sys.modules.get(f"generated.{snake}")
    assert pkg is not None, f"generated.{snake} not found in sys.modules"
    return {
        "Repository": getattr(pkg, f"{model_name}Repository"),
        "Create": getattr(pkg, f"{model_name}Create"),
        "Update": getattr(pkg, f"{model_name}Update"),
        "Filter": getattr(pkg, f"{model_name}Filter"),
        "LoadOptions": getattr(pkg, f"{model_name}LoadOptions"),
    }


def _to_snake(name: str) -> str:
    result: list[str] = []
    for i, c in enumerate(name):
        if c.isupper() and i > 0:
            result.append("_")
        result.append(c.lower())
    return "".join(result)


# ===========================================================================
# Tests — all use generated code imported from CLI output
# ===========================================================================


@pytest.mark.asyncio
async def test_create_user(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    dto = classes["Create"](username="alice", email="alice@example.com")
    user = await repo.create(dto)
    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.status == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_by_id(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    created = await repo.create(
        classes["Create"](username="bob", email="bob@example.com")
    )

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.username == "bob"


@pytest.mark.asyncio
async def test_get_by_id_not_found(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    result = await repo.get_by_id(99999)
    assert result is None


@pytest.mark.asyncio
async def test_create_many(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    dtos = [
        classes["Create"](username="user1", email="user1@example.com"),
        classes["Create"](username="user2", email="user2@example.com"),
        classes["Create"](username="user3", email="user3@example.com"),
    ]
    users = await repo.create_many(dtos)
    assert len(users) == 3
    assert all(u.id is not None for u in users)


@pytest.mark.asyncio
async def test_update(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    user = await repo.create(
        classes["Create"](username="charlie", email="charlie@example.com")
    )

    updated = await repo.update(classes["Update"](id=user.id, username="charles"))
    assert updated is not None
    assert updated.username == "charles"
    assert updated.email == "charlie@example.com"


@pytest.mark.asyncio
async def test_delete(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    user = await repo.create(
        classes["Create"](username="dave", email="dave@example.com")
    )

    result = await repo.delete(user.id)
    assert result is True

    fetched = await repo.get_by_id(user.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_soft_delete(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    user = await repo.create(
        classes["Create"](username="eve", email="eve@example.com")
    )

    deleted = await repo.soft_delete(user.id)
    assert deleted is not None
    assert deleted.deleted_at is not None

    # Should not appear in normal queries
    fetched = await repo.get_by_id(user.id)
    assert fetched is None

    # Should appear with include_deleted=True
    fetched = await repo.get_by_id(user.id, include_deleted=True)
    assert fetched is not None


@pytest.mark.asyncio
async def test_restore(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    user = await repo.create(
        classes["Create"](username="frank", email="frank@example.com")
    )

    await repo.soft_delete(user.id)
    restored = await repo.restore(user.id)
    assert restored is not None
    assert restored.deleted_at is None

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None


@pytest.mark.asyncio
async def test_get_many_basic(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    await repo.create(classes["Create"](username="x1", email="x1@example.com"))
    await repo.create(classes["Create"](username="x2", email="x2@example.com"))

    users = await repo.get_many()
    assert len(users) >= 2


@pytest.mark.asyncio
async def test_get_many_with_limit_offset(
    generated_package: Path, session: AsyncSession
):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    for i in range(5):
        await repo.create(
            classes["Create"](username=f"paged_{i}", email=f"paged_{i}@example.com")
        )

    page1 = await repo.get_many(limit=2, offset=0, order_by="username")
    page2 = await repo.get_many(limit=2, offset=2, order_by="username")
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].username != page2[0].username


@pytest.mark.asyncio
async def test_filter_string_eq(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    base_mod = sys.modules["generated.base"]
    StringFilter = base_mod.StringFilter

    await repo.create(
        classes["Create"](username="filter_test", email="ft@example.com")
    )
    await repo.create(
        classes["Create"](username="other", email="other@example.com")
    )

    results = await repo.get_many(
        filters=classes["Filter"](username=StringFilter(eq="filter_test"))
    )
    assert len(results) == 1
    assert results[0].username == "filter_test"


@pytest.mark.asyncio
async def test_filter_string_like(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    base_mod = sys.modules["generated.base"]
    StringFilter = base_mod.StringFilter

    await repo.create(
        classes["Create"](username="like_test_1", email="lt1@example.com")
    )
    await repo.create(
        classes["Create"](username="like_test_2", email="lt2@example.com")
    )
    await repo.create(
        classes["Create"](username="no_match", email="nm@example.com")
    )

    results = await repo.get_many(
        filters=classes["Filter"](username=StringFilter(like="like_test%"))
    )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_filter_string_in(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    base_mod = sys.modules["generated.base"]
    StringFilter = base_mod.StringFilter

    await repo.create(classes["Create"](username="in_1", email="in1@example.com"))
    await repo.create(classes["Create"](username="in_2", email="in2@example.com"))
    await repo.create(classes["Create"](username="in_3", email="in3@example.com"))

    results = await repo.get_many(
        filters=classes["Filter"](username=StringFilter(in_=["in_1", "in_3"]))
    )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_filter_enum(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    # Get the generated enum filter from the filters module
    filters_mod = sys.modules["generated.user.filters"]
    UserStatusFilter = filters_mod.UserStatusFilter

    await repo.create(
        classes["Create"](
            username="active_user", email="au@example.com", status=UserStatus.ACTIVE
        )
    )
    await repo.create(
        classes["Create"](
            username="banned_user", email="bu@example.com", status=UserStatus.BANNED
        )
    )

    results = await repo.get_many(
        filters=classes["Filter"](status=UserStatusFilter(eq=UserStatus.BANNED))
    )
    assert len(results) == 1
    assert results[0].username == "banned_user"


@pytest.mark.asyncio
async def test_count(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    await repo.create(classes["Create"](username="cnt1", email="cnt1@example.com"))
    await repo.create(classes["Create"](username="cnt2", email="cnt2@example.com"))

    count = await repo.count()
    assert count >= 2


@pytest.mark.asyncio
async def test_count_with_filter(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    base_mod = sys.modules["generated.base"]
    StringFilter = base_mod.StringFilter

    await repo.create(classes["Create"](username="cnt_f1", email="cntf1@example.com"))
    await repo.create(classes["Create"](username="cnt_f2", email="cntf2@example.com"))

    count = await repo.count(
        filters=classes["Filter"](username=StringFilter(eq="cnt_f1"))
    )
    assert count == 1


@pytest.mark.asyncio
async def test_soft_delete_excluded_from_count(
    generated_package: Path, session: AsyncSession
):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    base_mod = sys.modules["generated.base"]
    StringFilter = base_mod.StringFilter

    user = await repo.create(
        classes["Create"](username="cnt_sd", email="cntsd@example.com")
    )

    count_before = await repo.count(
        filters=classes["Filter"](username=StringFilter(eq="cnt_sd"))
    )
    assert count_before == 1

    await repo.soft_delete(user.id)
    count_after = await repo.count(
        filters=classes["Filter"](username=StringFilter(eq="cnt_sd"))
    )
    assert count_after == 0

    count_inc = await repo.count(
        filters=classes["Filter"](username=StringFilter(eq="cnt_sd")),
        include_deleted=True,
    )
    assert count_inc == 1


@pytest.mark.asyncio
async def test_ordering(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    base_mod = sys.modules["generated.base"]
    StringFilter = base_mod.StringFilter

    await repo.create(
        classes["Create"](username="zzz_order", email="z@example.com")
    )
    await repo.create(
        classes["Create"](username="aaa_order", email="a@example.com")
    )

    asc_results = await repo.get_many(
        filters=classes["Filter"](username=StringFilter(like="%_order")),
        order_by="username",
    )
    assert asc_results[0].username == "aaa_order"

    desc_results = await repo.get_many(
        filters=classes["Filter"](username=StringFilter(like="%_order")),
        order_by=[("username", "desc")],
    )
    assert desc_results[0].username == "zzz_order"


@pytest.mark.asyncio
async def test_policy_with_numeric_filter(
    generated_package: Path, session: AsyncSession
):
    user_classes = _get_classes("User")
    policy_classes = _get_classes("Policy")
    base_mod = sys.modules["generated.base"]
    NumericFilter = base_mod.NumericFilter

    user_repo = user_classes["Repository"](session)
    user = await user_repo.create(
        user_classes["Create"](username="policy_owner", email="po@example.com")
    )

    policy_repo = policy_classes["Repository"](session)
    await policy_repo.create(
        policy_classes["Create"](
            name="cheap", premium=Decimal("100.00"), user_id=user.id
        )
    )
    await policy_repo.create(
        policy_classes["Create"](
            name="expensive", premium=Decimal("5000.00"), user_id=user.id
        )
    )

    results = await policy_repo.get_many(
        filters=policy_classes["Filter"](
            premium=NumericFilter(gt=Decimal("1000.00"))
        )
    )
    assert len(results) == 1
    assert results[0].name == "expensive"


@pytest.mark.asyncio
async def test_load_options_relationships(
    generated_package: Path, session: AsyncSession
):
    user_classes = _get_classes("User")
    policy_classes = _get_classes("Policy")

    user_repo = user_classes["Repository"](session)
    user = await user_repo.create(
        user_classes["Create"](username="loader", email="loader@example.com")
    )

    policy_repo = policy_classes["Repository"](session)
    await policy_repo.create(
        policy_classes["Create"](
            name="pol1", premium=Decimal("100.00"), user_id=user.id
        )
    )

    # Load user with policies eagerly
    loaded = await user_repo.get_by_id(
        user.id,
        load_options=user_classes["LoadOptions"](policies=True),
    )
    assert loaded is not None
    assert len(loaded.policies) == 1


@pytest.mark.asyncio
async def test_composite_pk_operations(
    generated_package: Path, session: AsyncSession
):
    user_classes = _get_classes("User")
    policy_classes = _get_classes("Policy")
    rider_classes = _get_classes("PolicyRider")

    # Get the generated PK model
    rider_repo_mod = sys.modules["generated.policy_rider.repository"]
    PolicyRiderPK = rider_repo_mod.PolicyRiderPK

    # Create prerequisite data
    user_repo = user_classes["Repository"](session)
    user = await user_repo.create(
        user_classes["Create"](username="rider_owner", email="ro@example.com")
    )

    policy_repo = policy_classes["Repository"](session)
    policy = await policy_repo.create(
        policy_classes["Create"](
            name="rider_policy", premium=Decimal("500.00"), user_id=user.id
        )
    )

    # Test create with composite PK
    rider_repo = rider_classes["Repository"](session)
    dto = rider_classes["Create"](
        policy_id=policy.id,
        rider_id=1,
        name="Extra Coverage",
        extra_premium=Decimal("50.00"),
    )
    rider = await rider_repo.create(dto)
    assert rider.policy_id == policy.id
    assert rider.rider_id == 1

    # Get by composite PK
    pk = PolicyRiderPK(policy_id=policy.id, rider_id=1)
    fetched = await rider_repo.get_by_id(pk)
    assert fetched is not None
    assert fetched.name == "Extra Coverage"

    # Update by composite PK
    updated = await rider_repo.update(
        rider_classes["Update"](
            policy_id=policy.id, rider_id=1, name="Updated Coverage"
        )
    )
    assert updated is not None
    assert updated.name == "Updated Coverage"

    # Delete by composite PK
    result = await rider_repo.delete(pk)
    assert result is True

    fetched_after = await rider_repo.get_by_id(pk)
    assert fetched_after is None


@pytest.mark.asyncio
async def test_create_with_enum(generated_package: Path, session: AsyncSession):
    classes = _get_classes("User")
    repo = classes["Repository"](session)
    user = await repo.create(
        classes["Create"](
            username="enum_user", email="eu@example.com", status=UserStatus.BANNED
        )
    )
    assert user.status == UserStatus.BANNED

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.status == UserStatus.BANNED


@pytest.mark.asyncio
async def test_policy_soft_delete_lifecycle(
    generated_package: Path, session: AsyncSession
):
    """Test the full soft-delete lifecycle on a generated Policy repository."""
    user_classes = _get_classes("User")
    policy_classes = _get_classes("Policy")

    user_repo = user_classes["Repository"](session)
    user = await user_repo.create(
        user_classes["Create"](username="sd_owner", email="sd@example.com")
    )

    policy_repo = policy_classes["Repository"](session)
    policy = await policy_repo.create(
        policy_classes["Create"](
            name="to_delete",
            premium=Decimal("200.00"),
            user_id=user.id,
            status=PolicyStatus.ACTIVE,
        )
    )

    # Soft delete
    deleted = await policy_repo.soft_delete(policy.id)
    assert deleted is not None
    assert deleted.deleted_at is not None

    # Not visible in normal queries
    assert await policy_repo.get_by_id(policy.id) is None

    # Visible with include_deleted
    found = await policy_repo.get_by_id(policy.id, include_deleted=True)
    assert found is not None

    # Restore
    restored = await policy_repo.restore(policy.id)
    assert restored is not None
    assert restored.deleted_at is None

    # Visible again
    found_again = await policy_repo.get_by_id(policy.id)
    assert found_again is not None
    assert found_again.name == "to_delete"


@pytest.mark.asyncio
async def test_non_soft_deletable_model_raises(
    generated_package: Path, session: AsyncSession
):
    """Tag model has no deleted_at — soft_delete should raise."""
    classes = _get_classes("Tag")
    repo = classes["Repository"](session)
    tag = await repo.create(classes["Create"](name="test-tag"))

    with pytest.raises(NotImplementedError):
        await repo.soft_delete(tag.id)

    with pytest.raises(NotImplementedError):
        await repo.restore(tag.id)
