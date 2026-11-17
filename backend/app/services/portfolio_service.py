"""持股庫存的資料存取、所有權檢查與 Decimal 損益計算。"""

import asyncio
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PortfolioItem
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioItemResponse,
    PortfolioUpdate,
)
from app.services.market_service import get_stock_analysis

CENT = Decimal("0.01")


class PortfolioNotFoundError(Exception):
    pass


def _owned_item_query(item_id: int, user_id: int):
    return select(PortfolioItem).where(
        PortfolioItem.id == item_id,
        PortfolioItem.user_id == user_id,
    )


async def get_owned_item(session: AsyncSession, item_id: int, user_id: int) -> PortfolioItem:
    item = await session.scalar(_owned_item_query(item_id, user_id))
    if item is None:
        raise PortfolioNotFoundError
    return item


async def serialize_portfolio_item(
    item: PortfolioItem, analysis: dict | None = None
) -> PortfolioItemResponse:
    if analysis is None:
        analysis = await asyncio.to_thread(get_stock_analysis, item.stock_symbol)
    if not analysis["data"]:
        raise ValueError(f"{item.stock_symbol} 尚無可用收盤價")
    row = analysis["data"][-1]
    price = Decimal(str(row["close"]))
    price_as_of = str(row["date"])
    data_source = str(analysis["data_source"])
    cost_basis = item.average_cost * item.shares
    market_value = price * item.shares
    pnl = market_value - cost_basis
    return PortfolioItemResponse(
        id=item.id,
        stock_symbol=item.stock_symbol,
        stock_name=item.stock_name,
        average_cost=item.average_cost,
        shares=item.shares,
        current_price=price,
        market_value=market_value.quantize(CENT, rounding=ROUND_HALF_UP),
        unrealized_pnl=pnl.quantize(CENT, rounding=ROUND_HALF_UP),
        unrealized_return_pct=(pnl / cost_basis * Decimal(100)).quantize(
            CENT, rounding=ROUND_HALF_UP
        ),
        price_as_of=price_as_of,
        data_source=data_source,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def list_portfolio_items(
    session: AsyncSession, user_id: int
) -> list[PortfolioItemResponse]:
    items = list((await session.scalars(
        select(PortfolioItem).where(PortfolioItem.user_id == user_id).order_by(PortfolioItem.id)
    )).all())
    return [await serialize_portfolio_item(item) for item in items]


async def create_portfolio_item(
    session: AsyncSession,
    user_id: int,
    payload: PortfolioCreate,
) -> PortfolioItemResponse:
    analysis = await asyncio.to_thread(get_stock_analysis, payload.stock_symbol)
    item = PortfolioItem(
        user_id=user_id,
        stock_symbol=payload.stock_symbol,
        stock_name=analysis["name"],
        average_cost=payload.average_cost,
        shares=payload.shares,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return await serialize_portfolio_item(item, analysis)


async def update_portfolio_item(
    session: AsyncSession,
    item_id: int,
    user_id: int,
    payload: PortfolioUpdate,
) -> PortfolioItemResponse:
    item = await get_owned_item(session, item_id, user_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("至少提供一個要更新的庫存欄位")
    if any(value is None for value in updates.values()):
        raise ValueError("平均成本與持有股數不可為空")
    for field, value in updates.items():
        setattr(item, field, value)
    await session.commit()
    await session.refresh(item)
    return await serialize_portfolio_item(item)


async def delete_portfolio_item(session: AsyncSession, item_id: int, user_id: int) -> None:
    item = await get_owned_item(session, item_id, user_id)
    await session.delete(item)
    await session.commit()
