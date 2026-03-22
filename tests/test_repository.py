"""Integration tests for the repository layer."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.sample_models import (
    Policy,
    PolicyRider,
    PolicyStatus,
    User,
    UserStatus,
)

# We need to generate and import repos, but for integration tests
# we'll directly test the base repository mechanics by creating
# inline test repos.

import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pydantic import BaseModel


# --- Inline DTOs for testing ---


class UserCreate(BaseModel):
    username: str
    email: str
    status: UserStatus | None = None


class UserUpdate(BaseModel):
    id: int
    username: str | None = None
    email: str | None = None
    status: UserStatus | None = None


class UserFilter(BaseModel):
    username: "StringFilter | None" = None
    email: "StringFilter | None" = None
    status: "UserStatusFilter | None" = None


class StringFilter(BaseModel):
    eq: str | None = None
    neq: str | None = None
    like: str | None = None
    ilike: str | None = None
    in_: list[str] | None = None
    not_in: list[str] | None = None


class IntFilter(BaseModel):
    eq: int | None = None
    neq: int | None = None
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    in_: list[int] | None = None
    not_in: list[int] | None = None


class NumericFilter(BaseModel):
    eq: Decimal | None = None
    neq: Decimal | None = None
    gt: Decimal | None = None
    gte: Decimal | None = None
    lt: Decimal | None = None
    lte: Decimal | None = None
    in_: list[Decimal] | None = None
    not_in: list[Decimal] | None = None


class UserStatusFilter(BaseModel):
    eq: UserStatus | None = None
    neq: UserStatus | None = None
    in_: list[UserStatus] | None = None
    not_in: list[UserStatus] | None = None


class UserLoadOptions(BaseModel):
    load_strategy: "LoadStrategy | None" = None
    policies: "bool | None" = None
    profile: "bool | None" = None


class PolicyCreate(BaseModel):
    name: str
    premium: Decimal
    status: PolicyStatus | None = None
    user_id: int


class PolicyUpdate(BaseModel):
    id: int
    name: str | None = None
    premium: Decimal | None = None
    status: PolicyStatus | None = None
    user_id: int | None = None


class PolicyFilter(BaseModel):
    name: StringFilter | None = None
    premium: NumericFilter | None = None
    user_id: IntFilter | None = None


class PolicyLoadOptions(BaseModel):
    load_strategy: "LoadStrategy | None" = None
    claims: "bool | None" = None
    user: "bool | None" = None
    tags: "bool | None" = None


class PolicyRiderPK(BaseModel):
    policy_id: int
    rider_id: int


class PolicyRiderCreate(BaseModel):
    policy_id: int
    rider_id: int
    name: str
    extra_premium: Decimal


class PolicyRiderUpdate(BaseModel):
    policy_id: int
    rider_id: int
    name: str | None = None
    extra_premium: Decimal | None = None


class PolicyRiderFilter(BaseModel):
    pass


class PolicyRiderLoadOptions(BaseModel):
    load_strategy: "LoadStrategy | None" = None


# We need to import from generated base, but since it's a template string,
# we'll exec it to get the classes

import importlib.util
import tempfile
from pathlib import Path

from repodb.generators.base_repo_template import BASE_REPO_TEMPLATE


# Create a temp module from the base template
_temp_dir = tempfile.mkdtemp()
_base_path = Path(_temp_dir) / "base.py"
_base_path.write_text(BASE_REPO_TEMPLATE)
_spec = importlib.util.spec_from_file_location("test_base", str(_base_path))
_base_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base_mod)

BaseRepository = _base_mod.BaseRepository
LoadStrategy = _base_mod.LoadStrategy


# --- Test Repositories ---


class UserRepository(BaseRepository):
    model = User
    soft_deletable = True


class PolicyRepository(BaseRepository):
    model = Policy
    soft_deletable = True


class PolicyRiderRepository(BaseRepository):
    model = PolicyRider
    soft_deletable = False


# --- Tests ---


@pytest.mark.asyncio
async def test_create_user(session: AsyncSession):
    repo = UserRepository(session)
    dto = UserCreate(username="alice", email="alice@example.com")
    user = await repo.create(dto)
    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.status == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_by_id(session: AsyncSession):
    repo = UserRepository(session)
    dto = UserCreate(username="bob", email="bob@example.com")
    created = await repo.create(dto)

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.username == "bob"


@pytest.mark.asyncio
async def test_get_by_id_not_found(session: AsyncSession):
    repo = UserRepository(session)
    result = await repo.get_by_id(99999)
    assert result is None


@pytest.mark.asyncio
async def test_create_many(session: AsyncSession):
    repo = UserRepository(session)
    dtos = [
        UserCreate(username="user1", email="user1@example.com"),
        UserCreate(username="user2", email="user2@example.com"),
        UserCreate(username="user3", email="user3@example.com"),
    ]
    users = await repo.create_many(dtos)
    assert len(users) == 3
    assert all(u.id is not None for u in users)


@pytest.mark.asyncio
async def test_update(session: AsyncSession):
    repo = UserRepository(session)
    user = await repo.create(
        UserCreate(username="charlie", email="charlie@example.com")
    )

    updated = await repo.update(UserUpdate(id=user.id, username="charles"))
    assert updated is not None
    assert updated.username == "charles"
    assert updated.email == "charlie@example.com"  # unchanged


@pytest.mark.asyncio
async def test_delete(session: AsyncSession):
    repo = UserRepository(session)
    user = await repo.create(UserCreate(username="dave", email="dave@example.com"))

    result = await repo.delete(user.id)
    assert result is True

    fetched = await repo.get_by_id(user.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_soft_delete(session: AsyncSession):
    repo = UserRepository(session)
    user = await repo.create(UserCreate(username="eve", email="eve@example.com"))

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
async def test_restore(session: AsyncSession):
    repo = UserRepository(session)
    user = await repo.create(UserCreate(username="frank", email="frank@example.com"))

    await repo.soft_delete(user.id)
    restored = await repo.restore(user.id)
    assert restored is not None
    assert restored.deleted_at is None

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None


@pytest.mark.asyncio
async def test_get_many_basic(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="x1", email="x1@example.com"))
    await repo.create(UserCreate(username="x2", email="x2@example.com"))

    users = await repo.get_many()
    assert len(users) >= 2


@pytest.mark.asyncio
async def test_get_many_with_limit_offset(session: AsyncSession):
    repo = UserRepository(session)
    for i in range(5):
        await repo.create(
            UserCreate(username=f"paged_{i}", email=f"paged_{i}@example.com")
        )

    page1 = await repo.get_many(limit=2, offset=0, order_by="username")
    page2 = await repo.get_many(limit=2, offset=2, order_by="username")
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].username != page2[0].username


@pytest.mark.asyncio
async def test_filter_string_eq(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="filter_test", email="ft@example.com"))
    await repo.create(UserCreate(username="other", email="other@example.com"))

    results = await repo.get_many(
        filters=UserFilter(username=StringFilter(eq="filter_test"))
    )
    assert len(results) == 1
    assert results[0].username == "filter_test"


@pytest.mark.asyncio
async def test_filter_string_like(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="like_test_1", email="lt1@example.com"))
    await repo.create(UserCreate(username="like_test_2", email="lt2@example.com"))
    await repo.create(UserCreate(username="no_match", email="nm@example.com"))

    results = await repo.get_many(
        filters=UserFilter(username=StringFilter(like="like_test%"))
    )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_filter_string_in(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="in_1", email="in1@example.com"))
    await repo.create(UserCreate(username="in_2", email="in2@example.com"))
    await repo.create(UserCreate(username="in_3", email="in3@example.com"))

    results = await repo.get_many(
        filters=UserFilter(username=StringFilter(in_=["in_1", "in_3"]))
    )
    assert len(results) == 2


@pytest.mark.asyncio
async def test_filter_enum(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(
        UserCreate(
            username="active_user", email="au@example.com", status=UserStatus.ACTIVE
        )
    )
    await repo.create(
        UserCreate(
            username="banned_user", email="bu@example.com", status=UserStatus.BANNED
        )
    )

    results = await repo.get_many(
        filters=UserFilter(status=UserStatusFilter(eq=UserStatus.BANNED))
    )
    assert len(results) == 1
    assert results[0].username == "banned_user"


@pytest.mark.asyncio
async def test_count(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="cnt1", email="cnt1@example.com"))
    await repo.create(UserCreate(username="cnt2", email="cnt2@example.com"))

    count = await repo.count()
    assert count >= 2


@pytest.mark.asyncio
async def test_count_with_filter(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="cnt_f1", email="cntf1@example.com"))
    await repo.create(UserCreate(username="cnt_f2", email="cntf2@example.com"))

    count = await repo.count(filters=UserFilter(username=StringFilter(eq="cnt_f1")))
    assert count == 1


@pytest.mark.asyncio
async def test_soft_delete_excluded_from_count(session: AsyncSession):
    repo = UserRepository(session)
    user = await repo.create(UserCreate(username="cnt_sd", email="cntsd@example.com"))

    count_before = await repo.count(
        filters=UserFilter(username=StringFilter(eq="cnt_sd"))
    )
    assert count_before == 1

    await repo.soft_delete(user.id)
    count_after = await repo.count(
        filters=UserFilter(username=StringFilter(eq="cnt_sd"))
    )
    assert count_after == 0

    count_inc = await repo.count(
        filters=UserFilter(username=StringFilter(eq="cnt_sd")),
        include_deleted=True,
    )
    assert count_inc == 1


@pytest.mark.asyncio
async def test_ordering(session: AsyncSession):
    repo = UserRepository(session)
    await repo.create(UserCreate(username="zzz_order", email="z@example.com"))
    await repo.create(UserCreate(username="aaa_order", email="a@example.com"))

    asc_results = await repo.get_many(
        filters=UserFilter(username=StringFilter(like="%_order")),
        order_by="username",
    )
    assert asc_results[0].username == "aaa_order"

    desc_results = await repo.get_many(
        filters=UserFilter(username=StringFilter(like="%_order")),
        order_by=[("username", "desc")],
    )
    assert desc_results[0].username == "zzz_order"


@pytest.mark.asyncio
async def test_policy_with_numeric_filter(session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.create(
        UserCreate(username="policy_owner", email="po@example.com")
    )

    repo = PolicyRepository(session)
    await repo.create(
        PolicyCreate(name="cheap", premium=Decimal("100.00"), user_id=user.id)
    )
    await repo.create(
        PolicyCreate(name="expensive", premium=Decimal("5000.00"), user_id=user.id)
    )

    results = await repo.get_many(
        filters=PolicyFilter(premium=NumericFilter(gt=Decimal("1000.00")))
    )
    assert len(results) == 1
    assert results[0].name == "expensive"


@pytest.mark.asyncio
async def test_load_options_relationships(session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.create(
        UserCreate(username="loader", email="loader@example.com")
    )

    policy_repo = PolicyRepository(session)
    await policy_repo.create(
        PolicyCreate(name="pol1", premium=Decimal("100.00"), user_id=user.id)
    )

    # Load user with policies
    loaded = await user_repo.get_by_id(
        user.id,
        load_options=UserLoadOptions(policies=True),
    )
    assert loaded is not None
    assert len(loaded.policies) == 1


@pytest.mark.asyncio
async def test_composite_pk_operations(session: AsyncSession):
    # First create a user and policy
    user_repo = UserRepository(session)
    user = await user_repo.create(
        UserCreate(username="rider_owner", email="ro@example.com")
    )

    policy_repo = PolicyRepository(session)
    policy = await policy_repo.create(
        PolicyCreate(name="rider_policy", premium=Decimal("500.00"), user_id=user.id)
    )

    repo = PolicyRiderRepository(session)
    dto = PolicyRiderCreate(
        policy_id=policy.id,
        rider_id=1,
        name="Extra Coverage",
        extra_premium=Decimal("50.00"),
    )
    rider = await repo.create(dto)
    assert rider.policy_id == policy.id
    assert rider.rider_id == 1

    # Get by composite PK
    pk = PolicyRiderPK(policy_id=policy.id, rider_id=1)
    fetched = await repo.get_by_id(pk)
    assert fetched is not None
    assert fetched.name == "Extra Coverage"

    # Update by composite PK
    updated = await repo.update(
        PolicyRiderUpdate(policy_id=policy.id, rider_id=1, name="Updated Coverage")
    )
    assert updated is not None
    assert updated.name == "Updated Coverage"

    # Delete by composite PK
    result = await repo.delete(pk)
    assert result is True

    fetched_after = await repo.get_by_id(pk)
    assert fetched_after is None


@pytest.mark.asyncio
async def test_create_with_enum(session: AsyncSession):
    repo = UserRepository(session)
    user = await repo.create(
        UserCreate(
            username="enum_user", email="eu@example.com", status=UserStatus.BANNED
        )
    )
    assert user.status == UserStatus.BANNED

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.status == UserStatus.BANNED
