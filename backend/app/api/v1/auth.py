from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate_user,
    build_user_response,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    try:
        user = await register_user(session, payload)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="此 Email 已註冊") from None
    return build_user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    try:
        token, _ = await authenticate_user(session, payload.email, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email 或密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return token


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return build_user_response(current_user, current_user.risk_profile)
