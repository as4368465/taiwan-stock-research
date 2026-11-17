"""AI 每日額度的 API 回應模型。"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AiQuotaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usage_date: date
    user_used: int = Field(ge=0)
    user_limit: int = Field(ge=1)
    user_remaining: int = Field(ge=0)
    global_used: int = Field(ge=0)
    global_limit: int = Field(ge=1)
    global_remaining: int = Field(ge=0)
