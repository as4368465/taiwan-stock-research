"""經登入驗證的 AI 額度查詢 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.quota import AiQuotaResponse
from app.services.quota_service import get_ai_quota

router = APIRouter(prefix="/advisory", tags=["advisory-quota"])


@router.get("/quota", response_model=AiQuotaResponse)
async def read_ai_quota(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AiQuotaResponse:
    return await get_ai_quota(session, user.id)
