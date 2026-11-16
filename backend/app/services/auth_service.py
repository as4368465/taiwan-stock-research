"""註冊、登入與使用者查詢服務，不處理 HTTP 狀態碼。"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RiskType
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import RiskProfile, User
from app.schemas.auth import TokenResponse, UserCreate, UserResponse


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


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
