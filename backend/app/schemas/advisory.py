"""賣出診斷 AI 輸出與來源引用的 Pydantic v2 結構。"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SellAction(StrEnum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    HOLD = "HOLD"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SourceType(StrEnum):
    NEWS = "NEWS"
    TECHNICAL = "TECHNICAL"
    MARKET = "MARKET"
    INDUSTRY = "INDUSTRY"


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1, max_length=1200)
    url: str
    published_at: datetime


class SellDiagnosisDraft(BaseModel):
    """OpenAI 只回傳來源編號；原始引用內容由後端從 Provider 資料還原。"""

    model_config = ConfigDict(extra="forbid")

    action: SellAction
    confidence_level: ConfidenceLevel
    reasoning: str = Field(min_length=20, max_length=3000)
    source_ids: list[str] = Field(min_length=1, max_length=10)


class SellDiagnosisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: SellAction
    suggested_sell_price_min: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    suggested_sell_price_max: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    confidence_level: ConfidenceLevel
    reasoning: str = Field(min_length=1, max_length=4000)
    sources: list[SourceReference]
    disclaimer: str
