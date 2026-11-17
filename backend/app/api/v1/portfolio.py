"""已登入使用者的持股庫存 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioItemResponse,
    PortfolioUpdate,
)
from app.services.portfolio_service import (
    PortfolioNotFoundError,
    create_portfolio_item,
    delete_portfolio_item,
    list_portfolio_items,
    update_portfolio_item,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PortfolioItemResponse])
async def get_portfolio(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PortfolioItemResponse]:
    try:
        return await list_portfolio_items(session, user.id)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=f"無法取得持股行情：{error}") from error


@router.post("", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED)
async def add_portfolio_item(
    payload: PortfolioCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PortfolioItemResponse:
    try:
        return await create_portfolio_item(session, user.id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=f"股票資料來源暫時無法使用：{error}") from error


@router.put("/{item_id}", response_model=PortfolioItemResponse)
async def edit_portfolio_item(
    item_id: int,
    payload: PortfolioUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PortfolioItemResponse:
    try:
        return await update_portfolio_item(session, item_id, user.id, payload)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="找不到這筆持股") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=f"無法取得持股行情：{error}") from error


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_portfolio_item(
    item_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        await delete_portfolio_item(session, item_id, user.id)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="找不到這筆持股") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
