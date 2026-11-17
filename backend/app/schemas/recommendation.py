"""每日推薦 API 與 AI 選股輸出的 Pydantic v2 模型。"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.advisory import SourceReference


class DailyRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investment_budget: Decimal = Field(default=Decimal(100000), gt=0, max_digits=14, decimal_places=2)
    target_return_pct: Decimal | None = Field(default=None, gt=0, le=200, max_digits=6, decimal_places=2)
    max_loss_pct: Decimal | None = Field(default=None, gt=0, le=50, max_digits=5, decimal_places=2)


class StockRecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=4, max_length=6)
    name: str = Field(min_length=1, max_length=100)
    current_price: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    suggested_buy_price_min: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    suggested_buy_price_max: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    suggested_shares: int = Field(ge=0)
    target_sell_price: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    stop_loss_price: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    reasoning: str = Field(min_length=20, max_length=3000)
    sources: list[SourceReference] = Field(min_length=1, max_length=10)


class DailyRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    user_risk_type: str = Field(min_length=1, max_length=40)
    market_summary: str = Field(min_length=1, max_length=1000)
    recommendations: list[StockRecommendationItem] = Field(min_length=3, max_length=3)
    disclaimer: str


class ScreenerCandidate(BaseModel):
    """服務與 Agent 之間使用的量化初篩結果，非公開 API 回應。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    current_price: Decimal
    ma5: Decimal
    ma20: Decimal
    ma60: Decimal
    volatility_20d_pct: Decimal
    trend_score: int = Field(ge=0, le=100)
    data_date: str
    data_source: str
    is_demo_data: bool


class RecommendationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    reasoning: str = Field(min_length=20, max_length=3000)
    source_ids: list[str] = Field(min_length=1, max_length=10)


class DailyRecommendationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selections: list[RecommendationChoice] = Field(min_length=3, max_length=3)
