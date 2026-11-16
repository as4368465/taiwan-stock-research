"""風險問卷、答案與評估結果的 Pydantic v2 模型。"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RiskType

RiskAnswerValue = Annotated[int, Field(ge=1, le=5)]


class RiskOption(BaseModel):
    value: RiskAnswerValue
    label: str


class RiskQuestion(BaseModel):
    id: str
    prompt: str
    options: list[RiskOption]


class RiskQuestionsResponse(BaseModel):
    questions: list[RiskQuestion]


class RiskAssessmentSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, RiskAnswerValue]
    target_return_pct: Decimal | None = Field(default=None, gt=0, le=100, max_digits=6, decimal_places=2)
    max_drawdown_pct: Decimal | None = Field(default=None, gt=0, le=100, max_digits=6, decimal_places=2)


class RiskProfileResponse(BaseModel):
    id: int
    risk_score: int = Field(ge=5, le=25)
    risk_type: RiskType
    risk_type_label: str
    target_return_pct: float
    max_drawdown_pct: float
    suggested_target_return_min_pct: float
    suggested_target_return_max_pct: float | None
    suggested_drawdown_min_pct: float
    suggested_drawdown_max_pct: float
    guidance: str
    answers: dict[str, RiskAnswerValue]
    updated_at: datetime
