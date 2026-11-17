"""持股庫存 API 的 Pydantic v2 請求與回應模型。"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

StockSymbol = Annotated[str, Field(pattern=r"^\d{4,6}$")]
PositivePrice = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=4)]
PositiveShares = Annotated[int, Field(gt=0, le=100_000_000)]


class PortfolioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_symbol: StockSymbol
    average_cost: PositivePrice
    shares: PositiveShares


class PortfolioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average_cost: PositivePrice | None = None
    shares: PositiveShares | None = None


class PortfolioItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_symbol: str
    stock_name: str
    average_cost: Decimal
    shares: int
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_return_pct: Decimal
    price_as_of: str
    data_source: str
    created_at: datetime
    updated_at: datetime
