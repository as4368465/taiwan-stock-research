"""風險問卷題庫、確定性計分與使用者風險屬性服務。"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RiskType
from app.db.models import RiskProfile
from app.schemas.risk import RiskAssessmentSubmit, RiskProfileResponse
from app.services.auth_service import risk_type_label

QUESTION_BANK = (
    {
        "id": "experience_years",
        "prompt": "您持續參與台股投資的經驗大約有多久？",
        "options": [
            {"value": 1, "label": "尚未投資或未滿 1 年"},
            {"value": 2, "label": "1 至未滿 3 年"},
            {"value": 3, "label": "3 至未滿 5 年"},
            {"value": 4, "label": "5 至未滿 10 年"},
            {"value": 5, "label": "10 年以上"},
        ],
    },
    {
        "id": "loss_tolerance",
        "prompt": "單筆投資暫時虧損時，您仍能依原計畫持有的最大幅度約為？",
        "options": [
            {"value": 1, "label": "低於 3%"},
            {"value": 2, "label": "3% 至未滿 5%"},
            {"value": 3, "label": "5% 至未滿 10%"},
            {"value": 4, "label": "10% 至未滿 20%"},
            {"value": 5, "label": "20% 以上"},
        ],
    },
    {
        "id": "investment_goal",
        "prompt": "以下哪一項最接近您目前的投資目標？",
        "options": [
            {"value": 1, "label": "優先保本與維持資金穩定"},
            {"value": 2, "label": "以股息或穩定收益為主"},
            {"value": 3, "label": "兼顧收益與資產成長"},
            {"value": 4, "label": "追求高於市場平均的資本成長"},
            {"value": 5, "label": "追求較高成長，能接受較大波動"},
        ],
    },
    {
        "id": "market_drop_reaction",
        "prompt": "若大盤單日下跌 5%，您最可能採取哪種行動？",
        "options": [
            {"value": 1, "label": "大幅減碼，優先降低波動"},
            {"value": 2, "label": "賣出部分持股，等待市場穩定"},
            {"value": 3, "label": "先觀察，不急著改變部位"},
            {"value": 4, "label": "依原計畫分批投入"},
            {"value": 5, "label": "若基本條件未變，考慮積極加碼"},
        ],
    },
    {
        "id": "investment_horizon",
        "prompt": "這筆投資資金預計多久之後才會需要使用？",
        "options": [
            {"value": 1, "label": "少於 1 年"},
            {"value": 2, "label": "1 至未滿 3 年"},
            {"value": 3, "label": "3 至未滿 5 年"},
            {"value": 4, "label": "5 至未滿 10 年"},
            {"value": 5, "label": "10 年以上或沒有明確期限"},
        ],
    },
)

QUESTION_IDS = frozenset(question["id"] for question in QUESTION_BANK)
RISK_RECOMMENDATIONS = {
    RiskType.CONSERVATIVE: {
        "target_default": Decimal("7.00"),
        "target_min": Decimal("6.00"),
        "target_max": Decimal("8.00"),
        "drawdown_default": Decimal("5.00"),
        "drawdown_min": Decimal("0.00"),
        "drawdown_max": Decimal("5.00"),
        "guidance": "重視資金穩定；此區間為問卷參考，不代表獲利承諾。",
    },
    RiskType.MODERATE: {
        "target_default": Decimal("12.50"),
        "target_min": Decimal("10.00"),
        "target_max": Decimal("15.00"),
        "drawdown_default": Decimal("10.00"),
        "drawdown_min": Decimal("5.00"),
        "drawdown_max": Decimal("10.00"),
        "guidance": "兼顧收益與波動；請依資金用途和實際承受度調整。",
    },
    RiskType.AGGRESSIVE: {
        "target_default": Decimal("22.00"),
        "target_min": Decimal("20.00"),
        "target_max": None,
        "drawdown_default": Decimal("17.50"),
        "drawdown_min": Decimal("15.00"),
        "drawdown_max": Decimal("20.00"),
        "guidance": "可承受較高波動；高目標報酬伴隨較大風險，不保證達成。",
    },
}


def get_questions() -> dict:
    return {"questions": list(QUESTION_BANK)}


def calculate_risk_score(answers: dict[str, int]) -> int:
    if set(answers) != QUESTION_IDS:
        raise ValueError("請完整回答全部 5 題")
    if any(not 1 <= score <= 5 for score in answers.values()):
        raise ValueError("每題答案必須介於 1 到 5")
    return sum(answers.values())


def classify_risk_score(score: int) -> RiskType:
    if not 5 <= score <= 25:
        raise ValueError("風險分數必須介於 5 到 25")
    if score <= 11:
        return RiskType.CONSERVATIVE
    if score <= 18:
        return RiskType.MODERATE
    return RiskType.AGGRESSIVE


def _decimal_pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_profile_response(profile: RiskProfile) -> RiskProfileResponse:
    recommendation = RISK_RECOMMENDATIONS[profile.risk_type]
    answer_details = profile.answers_json.get("answers", profile.answers_json)
    return RiskProfileResponse(
        id=profile.id,
        risk_score=profile.risk_score,
        risk_type=profile.risk_type,
        risk_type_label=risk_type_label(profile.risk_type),
        target_return_pct=float(profile.target_return_pct),
        max_drawdown_pct=float(profile.max_drawdown_pct),
        suggested_target_return_min_pct=float(recommendation["target_min"]),
        suggested_target_return_max_pct=(
            float(recommendation["target_max"]) if recommendation["target_max"] is not None else None
        ),
        suggested_drawdown_min_pct=float(recommendation["drawdown_min"]),
        suggested_drawdown_max_pct=float(recommendation["drawdown_max"]),
        guidance=recommendation["guidance"],
        answers=answer_details,
        updated_at=profile.updated_at,
    )


async def assess_user(
    session: AsyncSession,
    user_id: int,
    payload: RiskAssessmentSubmit,
) -> RiskProfileResponse:
    score = calculate_risk_score(payload.answers)
    risk_type = classify_risk_score(score)
    recommendation = RISK_RECOMMENDATIONS[risk_type]
    target_return = _decimal_pct(
        payload.target_return_pct or recommendation["target_default"]
    )
    max_drawdown = _decimal_pct(
        payload.max_drawdown_pct or recommendation["drawdown_default"]
    )

    profile = await session.scalar(
        select(RiskProfile).where(RiskProfile.user_id == user_id)
    )
    if profile is None:
        profile = RiskProfile(user_id=user_id)
        session.add(profile)

    profile.risk_score = score
    profile.risk_type = risk_type
    profile.target_return_pct = target_return
    profile.max_drawdown_pct = max_drawdown
    profile.answers_json = {"version": 1, "answers": payload.answers}
    await session.commit()
    await session.refresh(profile)
    return to_profile_response(profile)


async def get_user_profile(session: AsyncSession, user_id: int) -> RiskProfileResponse | None:
    profile = await session.scalar(
        select(RiskProfile).where(RiskProfile.user_id == user_id)
    )
    return to_profile_response(profile) if profile else None
