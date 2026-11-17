"""註冊、登入與使用者查詢服務，不處理 HTTP 狀態碼。"""

from __future__ import annotations

import secrets
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RiskType
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import PortfolioItem, RiskProfile, User
from app.schemas.auth import TokenResponse, UserCreate, UserResponse


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


DEMO_EMAIL = "demo@quantguard.tw"
DEMO_NAME = "QuantGuard 展示帳號"
DEMO_ANSWERS = {
    "experience_years": 3,
    "loss_tolerance": 3,
    "investment_goal": 3,
    "market_drop_reaction": 3,
    "investment_horizon": 3,
}
DEMO_HOLDINGS = (
    ("2330", "台積電", Decimal("1250.00"), 10),
    ("2317", "鴻海", Decimal("160.00"), 100),
)
_DEMO_PASSWORD_HASH: str | None = None


def _demo_password_hash() -> str:
    global _DEMO_PASSWORD_HASH
    if _DEMO_PASSWORD_HASH is None:
        _DEMO_PASSWORD_HASH = hash_password(secrets.token_urlsafe(48))
    return _DEMO_PASSWORD_HASH


async def ensure_demo_account(session: AsyncSession) -> User:
    """確保展示帳號、穩健型風險屬性與兩筆示範持股存在。"""
    user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        # Demo login has no password form; store only an unknown random password hash.
        user = User(
            email=DEMO_EMAIL,
            hashed_password=_demo_password_hash(),
            full_name=DEMO_NAME,
        )
        session.add(user)
        await session.flush()

    profile = await session.scalar(
        select(RiskProfile).where(RiskProfile.user_id == user.id)
    )
    if profile is None:
        profile = RiskProfile(
            user_id=user.id,
            risk_score=sum(DEMO_ANSWERS.values()),
            risk_type=RiskType.MODERATE,
            target_return_pct=Decimal("12.50"),
            max_drawdown_pct=Decimal("10.00"),
            answers_json={"version": 1, "answers": DEMO_ANSWERS},
        )
        session.add(profile)

    existing_symbols = set(
        (await session.scalars(
            select(PortfolioItem.stock_symbol).where(PortfolioItem.user_id == user.id)
        )).all()
    )
    for symbol, name, average_cost, shares in DEMO_HOLDINGS:
        if symbol not in existing_symbols:
            session.add(
                PortfolioItem(
                    user_id=user.id,
                    stock_symbol=symbol,
                    stock_name=name,
                    average_cost=average_cost,
                    shares=shares,
                )
            )

    await session.commit()
    await session.refresh(user)
    return user


async def create_demo_login_token(session: AsyncSession) -> TokenResponse:
    """發放共用展示帳號 Token；各訪客的 AI 使用仍合併計入同一帳號額度。"""
    user = await ensure_demo_account(session)
    return TokenResponse(access_token=create_access_token(str(user.id)))


def build_user_response(user: User, profile: RiskProfile | None = None) -> UserResponse:
    risk_type = profile.risk_type if profile else None
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
        risk_score=profile.risk_score if profile else None,
        risk_type=risk_type,
        risk_type_label=risk_type_label(risk_type) if risk_type else None,
    )


def risk_type_label(risk_type: RiskType) -> str:
    return {
        RiskType.CONSERVATIVE: "保守型投資者",
        RiskType.MODERATE: "穩健型投資者",
        RiskType.AGGRESSIVE: "積極型投資者",
    }[risk_type]


async def register_user(session: AsyncSession, payload: UserCreate) -> User:
    existing_user = await session.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise DuplicateEmailError from None

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DuplicateEmailError from error
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> tuple[TokenResponse, User]:
    user = await session.scalar(
        select(User).options(selectinload(User.risk_profile)).where(User.email == email)
    )
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError from None
    return TokenResponse(access_token=create_access_token(str(user.id))), user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.scalar(
        select(User).options(selectinload(User.risk_profile)).where(User.id == user_id)
    )
