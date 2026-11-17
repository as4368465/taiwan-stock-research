import asyncio
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from app.agents.daily_recommender_agent import RecommendationUnavailableError
from app.api.v1 import advisory
from app.core.config import settings
from app.core.enums import AiUsageEndpoint
from app.core.security import create_access_token
from app.db.models import AiUsageLog, User
from app.db.session import create_tables
from app.main import create_app
from app.services import quota_service
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def test_cors_origins_parses_multiple_frontend_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "cors_origins",
        "https://quantguard.example, https://preview.example/",
    )

    assert settings.allowed_origins == [
        "https://quantguard.example",
        "https://preview.example/",
    ]


def test_new_ai_usage_deletes_logs_older_than_30_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date(2026, 11, 17)
    monkeypatch.setattr(quota_service, "taipei_today", lambda: today)

    async def run_test() -> None:
        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
        )
        test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
        await create_tables(test_engine)
        async with test_session_factory() as session:
            user = User(
                email="retention@example.com",
                hashed_password="unused-in-this-test",
                full_name="retention",
            )
            session.add(user)
            await session.commit()
            session.add(
                AiUsageLog(
                    user_id=user.id,
                    endpoint_type=AiUsageEndpoint.DAILY_RECOMMENDATION,
                    usage_date=today - timedelta(days=31),
                )
            )
            await session.commit()

            await quota_service.consume_ai_quota(
                session, user.id, AiUsageEndpoint.SELL_DIAGNOSIS
            )
            old_count = await session.scalar(
                select(func.count(AiUsageLog.id)).where(
                    AiUsageLog.usage_date < today - timedelta(days=30)
                )
            )
            assert old_count == 0
        await test_engine.dispose()

    asyncio.run(run_test())


@pytest.fixture
def client() -> Iterator[TestClient]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    with TestClient(create_app(test_engine, test_session_factory)) as test_client:
        yield test_client


def test_user_quota_returns_429_and_resets_on_next_taipei_day(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "user_daily_ai_limit", 1)
    monkeypatch.setattr(settings, "global_daily_ai_limit", 50)
    today = date(2026, 11, 17)
    monkeypatch.setattr(quota_service, "taipei_today", lambda: today)

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "quota@example.com",
            "password": "safe-password-123",
            "full_name": "quota-test",
        },
    )
    assert registration.status_code == 201
    token = create_access_token(str(registration.json()["id"]))
    headers = {"Authorization": f"Bearer {token}"}

    async def fake_recommendation(*_args, **_kwargs):
        raise RecommendationUnavailableError("測試不呼叫外部 AI。")

    monkeypatch.setattr(advisory, "recommend_daily", fake_recommendation)

    first_request = client.post(
        "/api/v1/advisory/daily-recommendations",
        headers=headers,
        json={"investment_budget": 10000},
    )
    assert first_request.status_code == 503

    blocked_request = client.post(
        "/api/v1/advisory/daily-recommendations",
        headers=headers,
        json={"investment_budget": 10000},
    )
    assert blocked_request.status_code == 429
    assert "今日免費 AI 分析額度（1 次）已達上限" in blocked_request.json()["detail"]

    usage_today = client.get("/api/v1/advisory/quota", headers=headers)
    assert usage_today.status_code == 200
    assert usage_today.json()["user_used"] == 1
    assert usage_today.json()["user_remaining"] == 0
    assert usage_today.json()["global_used"] == 1
    assert usage_today.json()["global_remaining"] == 49

    next_day = today + timedelta(days=1)
    monkeypatch.setattr(quota_service, "taipei_today", lambda: next_day)

    usage_next_day = client.get("/api/v1/advisory/quota", headers=headers)
    assert usage_next_day.status_code == 200
    assert usage_next_day.json()["usage_date"] == next_day.isoformat()
    assert usage_next_day.json()["user_used"] == 0
    assert usage_next_day.json()["user_remaining"] == 1

    next_day_request = client.post(
        "/api/v1/advisory/daily-recommendations",
        headers=headers,
        json={"investment_budget": 10000},
    )
    assert next_day_request.status_code == 503
