"""投資術語小百科 API 的結構化資料模型。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class GlossaryCategory(StrEnum):
    BASIC = "基礎交易"
    CANDLE = "K線型態"
    INDICATOR = "技術指標"
    RISK = "風險控管"


class GlossaryTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=40)
    category: GlossaryCategory
    summary: str = Field(min_length=1, max_length=300)
    practical_tip: str = Field(min_length=1, max_length=500)
    risk_warning: str = Field(min_length=1, max_length=500)


class GlossaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: list[GlossaryTerm]
    total: int = Field(ge=0)
