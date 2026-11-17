"""確定性技術指標快照的 Pydantic 結構。"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CandleFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    body_ratio_pct: Decimal
    upper_shadow_ratio_pct: Decimal
    lower_shadow_ratio_pct: Decimal
    candle_color: str
    pattern: str


class TechnicalIndicatorSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_date: str
    candles: list[CandleFeature] = Field(max_length=3)
    volume_ratio: Decimal | None
    volume_signal: str
    rsi14: Decimal | None
    rsi_signal: str
    macd_dif: Decimal | None
    macd_dea: Decimal | None
    macd_histogram: Decimal | None
    macd_signal: str
