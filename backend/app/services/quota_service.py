"""依台北日期控管個人與全站 AI 每日使用額度。"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import AiUsageEndpoint
from app.db.models import AiUsageLog
from app.schemas.quota import AiQuotaResponse

TAIPEI_TIMEZONE = ZoneInfo("Asia/Taipei")


class QuotaExceededError(Exception):
    """目前用戶或全站已用完當日 AI 額度。"""


def taipei_today() -> date:
    return datetime.now(TAIPEI_TIMEZONE).date()


async def _usage_counts(
    session: AsyncSession,
    user_id: int,
    usage_date: date,
) -> tuple[int, int]:
    user_used = await session.scalar(
        select(func.count(AiUsageLog.id)).where(
            AiUsageLog.user_id == user_id,
            AiUsageLog.usage_date == usage_date,
        )
    )
    global_used = await session.scalar(
        select(func.count(AiUsageLog.id)).where(AiUsageLog.usage_date == usage_date)
    )
    return int(user_used or 0), int(global_used or 0)


async def get_ai_quota(session: AsyncSession, user_id: int) -> AiQuotaResponse:
    """回傳目前用戶與全站今日已用、上限和剩餘次數。"""
    usage_date = taipei_today()
    user_used, global_used = await _usage_counts(session, user_id, usage_date)
    return AiQuotaResponse(
        usage_date=usage_date,
        user_used=user_used,
        user_limit=settings.user_daily_ai_limit,
        user_remaining=max(settings.user_daily_ai_limit - user_used, 0),
        global_used=global_used,
        global_limit=settings.global_daily_ai_limit,
        global_remaining=max(settings.global_daily_ai_limit - global_used, 0),
    )


async def consume_ai_quota(
    session: AsyncSession,
    user_id: int,
    endpoint_type: AiUsageEndpoint,
) -> AiQuotaResponse:
    """先檢查額度，再記錄一次 AI 功能請求；超額時不建立使用紀錄。"""
    usage_date = taipei_today()

    if session.bind and session.bind.dialect.name == "postgresql":
        # PostgreSQL advisory transaction lock prevents different workers from
        # passing the global read-check-insert sequence at the same time.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:quota_day))"),
            {"quota_day": usage_date.isoformat()},
        )
    elif session.bind and session.bind.dialect.name == "sqlite":
        # SQLite has no row/advisory locks; an immediate write transaction
        # serializes quota reservations across requests sharing the database.
        await session.execute(text("BEGIN IMMEDIATE"))

    user_used, global_used = await _usage_counts(session, user_id, usage_date)
    if user_used >= settings.user_daily_ai_limit:
        await session.rollback()
        raise QuotaExceededError(
            f"今日免費 AI 分析額度（{settings.user_daily_ai_limit} 次）已達上限，"
            "請明日再試；本機自用可在 .env 調高 USER_DAILY_AI_LIMIT，並設定自己的 OpenAI API Key。"
        )
    if global_used >= settings.global_daily_ai_limit:
        await session.rollback()
        raise QuotaExceededError("今日全站 AI 體驗額度已用完，請明日再試。")

    session.add(
        AiUsageLog(
            user_id=user_id,
            endpoint_type=endpoint_type,
            usage_date=usage_date,
        )
    )
    await session.execute(
        delete(AiUsageLog).where(AiUsageLog.usage_date < usage_date - timedelta(days=30))
    )
    await session.commit()
    return await get_ai_quota(session, user_id)
