from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.risk import (
    RiskAssessmentSubmit,
    RiskProfileResponse,
    RiskQuestionsResponse,
)
from app.services.risk_service import assess_user, get_questions, get_user_profile

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/questions", response_model=RiskQuestionsResponse)
def risk_questions() -> dict:
    return get_questions()


@router.post("/assess", response_model=RiskProfileResponse)
async def assess_risk(
    payload: RiskAssessmentSubmit,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskProfileResponse:
    try:
        return await assess_user(session, current_user.id, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/profile", response_model=RiskProfileResponse)
async def risk_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskProfileResponse:
    profile = await get_user_profile(session, current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="尚未完成風險屬性評估")
    return profile
