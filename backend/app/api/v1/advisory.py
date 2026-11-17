"""登入使用者持股的賣出診斷 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sell_advisor_agent import AdvisoryUnavailableError, diagnose_sell
from app.api.v1.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.advisory import SellDiagnosisResponse
from app.services.portfolio_service import PortfolioNotFoundError, get_owned_item

router = APIRouter(prefix="/advisory", tags=["advisory"])


@router.post("/sell-diagnosis/{item_id}", response_model=SellDiagnosisResponse)
async def sell_diagnosis(
    item_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SellDiagnosisResponse:
    try:
        item = await get_owned_item(session, item_id, user.id)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="找不到這筆持股") from None
    try:
        return await diagnose_sell(session, user, item)
    except AdvisoryUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
