"""Sample SQLAlchemy models for testing RepoDB."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Table, Column, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


class PolicyStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# Association table for M2M
policy_tags = Table(
    "policy_tags",
    Base.metadata,
    Column("policy_id", Integer, ForeignKey("policies.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100))
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.ACTIVE)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    policies: Mapped[list["Policy"]] = relationship(back_populates="user")
    profile: Mapped["Profile | None"] = relationship(back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bio: Mapped[str | None] = mapped_column(String(500), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(200), default=None)

    user: Mapped["User"] = relationship(back_populates="profile")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    premium: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[PolicyStatus] = mapped_column(default=PolicyStatus.DRAFT)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped["User"] = relationship(back_populates="policies")
    claims: Mapped[list["Claim"]] = relationship(back_populates="policy")
    tags: Mapped[list["Tag"]] = relationship(secondary=policy_tags, back_populates="policies")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    filed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    policy: Mapped["Policy"] = relationship(back_populates="claims")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))

    policies: Mapped[list["Policy"]] = relationship(secondary=policy_tags, back_populates="tags")


# Composite PK model
class PolicyRider(Base):
    __tablename__ = "policy_riders"

    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), primary_key=True)
    rider_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    extra_premium: Mapped[Decimal] = mapped_column(Numeric(10, 2))


# Single-table inheritance
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    __mapper_args__ = {
        "polymorphic_on": "type",
        "polymorphic_identity": "base",
    }


class EmailNotification(Notification):
    email_subject: Mapped[str | None] = mapped_column(String(200), default=None)

    __mapper_args__ = {
        "polymorphic_identity": "email",
    }


class SMSNotification(Notification):
    phone_number: Mapped[str | None] = mapped_column(String(20), default=None)

    __mapper_args__ = {
        "polymorphic_identity": "sms",
    }
