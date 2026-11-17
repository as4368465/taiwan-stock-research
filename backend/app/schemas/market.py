"""市場與個股 API 使用的 Pydantic v2 回應模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StockMatch(APIModel):
    stock_id: str
    stock_name: str


class StockSearchResponse(APIModel):
    query: str
    results: list[StockMatch]


class PricePoint(APIModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ma5: float | None = None
    ma20: float | None = None
    ma60: float | None = None


class StockAnalysisResponse(APIModel):
    symbol: str
    name: str
    is_demo_data: bool
    data_source: str
    latest_data_date: str | None
    is_realtime: bool
    updated_at: datetime
    notice: str
    latest_close: float | None
    data: list[PricePoint]


class MarketPoint(APIModel):
    time: str
    value: float


class MarketOverviewResponse(APIModel):
    symbol: str
    name: str
    is_demo_data: bool
    data_source: str
    latest_data_date: str | None
    updated_at: datetime
    latest_value: float
    session_open: float
    session_high: float
    session_low: float
    data: list[MarketPoint]
    notice: str
