"""使用者與風險屬性的 SQLAlchemy ORM 模型。"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.enums import RiskType


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255, collation="NOCASE"), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    risk_profile: Mapped["RiskProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    portfolio_items: Mapped[list["PortfolioItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_type: Mapped[RiskType] = mapped_column(
        Enum(
            RiskType,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    target_return_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    answers_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="risk_profile")


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stock_symbol: Mapped[str] = mapped_column(String(6), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="portfolio_items")
