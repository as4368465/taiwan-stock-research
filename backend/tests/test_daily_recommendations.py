from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from app.agents import daily_recommender_agent
from app.core.enums import RiskType
from app.core.security import create_access_token
from app.main import create_app
from app.schemas.advisory import SourceReference
from app.schemas.recommendation import (
    DailyRecommendationDraft,
    RecommendationChoice,
    ScreenerCandidate,
)
from app.services import screener_service
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client() -> Iterator[TestClient]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    with TestClient(create_app(test_engine, test_session_factory)) as test_client:
        yield test_client


def register_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "daily@example.com", "password": "safe-password-123", "full_name": "daily"},
    )
    assert response.status_code == 201
    return create_access_token(str(response.json()["id"]))


def mock_analysis(symbol: str, close: float = 100) -> dict:
    rows = []
    for day in range(1, 81):
        value = close * (0.8 + day / 400)
        rows.append({
            "date": (datetime(2026, 8, 1) + timedelta(days=day - 1)).date().isoformat(),
            "close": value,
            "ma5": value * 0.99,
            "ma20": value * 0.98,
            "ma60": value * 0.95,
        })
    return {
        "symbol": symbol,
        "name": f"測試{symbol}",
        "is_demo_data": False,
        "data_source": "Mock 行情來源",
        "data": rows,
    }


def test_screener_excludes_stock_above_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        screener_service,
        "get_stock_analysis",
        lambda symbol: mock_analysis(symbol, 500 if symbol == "2330" else 50),
    )

    candidates, summary = screener_service.screen_candidates(
        Decimal(300), risk_type=RiskType.MODERATE
    )

    assert candidates
    assert all(candidate.current_price <= Decimal(300) for candidate in candidates)
    assert all(candidate.symbol != "2330" for candidate in candidates)
    assert "核心觀察池" in summary


def test_daily_recommendation_api_returns_grounded_three_and_calculated_prices(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        ScreenerCandidate(
            symbol=f"{2330 + index}",
            name=f"候選股{index + 1}",
            current_price=Decimal(100),
            ma5=Decimal(99),
            ma20=Decimal(98),
            ma60=Decimal(95),
            volatility_20d_pct=Decimal("8.50"),
            trend_score=80 - index,
            data_date="2026-11-16",
            data_source="Mock 行情來源",
            is_demo_data=False,
        )
        for index in range(5)
    ]
    monkeypatch.setattr(
        daily_recommender_agent,
        "screen_candidates",
        lambda budget, risk, limit: (candidates[:limit], "測試觀察池摘要。"),
    )
    monkeypatch.setattr(
        daily_recommender_agent.settings,
        "openai_api_key",
        SecretStr("test-key"),
    )

    def fake_news(symbol: str, limit: int) -> dict:
        return {"news": [{
            "title": f"{symbol} 公司公告測試",
            "summary": "由測試資料提供的公開消息摘要。",
            "url": f"https://example.com/{symbol}",
            "published_at": "2026-11-16T08:00:00",
        }]}

    monkeypatch.setattr(daily_recommender_agent, "get_stock_news", fake_news)

    def fake_llm(context: dict) -> DailyRecommendationDraft:
        assert len(context["候選股"]) == 5
        return DailyRecommendationDraft(selections=[
            RecommendationChoice(
                symbol=candidate.symbol,
                reasoning="此候選股的均線排列與量化趨勢分數符合本次風險條件，新聞可作為近期公司事件線索。",
                source_ids=["S1", "S2"],
            )
            for candidate in candidates[:3]
        ])

    monkeypatch.setattr(daily_recommender_agent, "_generate_with_openai", fake_llm)
    assert client.post(
        "/api/v1/advisory/daily-recommendations",
        json={"investment_budget": 90000},
    ).status_code == 401
    token = register_token(client)

    response = client.post(
        "/api/v1/advisory/daily-recommendations",
        headers={"Authorization": f"Bearer {token}"},
        json={"investment_budget": 90000, "target_return_pct": 10, "max_loss_pct": 5},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["recommendations"]) == 3
    first = body["recommendations"][0]
    assert first["suggested_shares"] == 300
    assert Decimal(first["suggested_buy_price_min"]) == Decimal("99.00")
    assert Decimal(first["suggested_buy_price_max"]) == Decimal(100)
    assert Decimal(first["target_sell_price"]) == Decimal("109.45")
    assert Decimal(first["stop_loss_price"]) == Decimal("94.53")
    assert {source["source_type"] for source in first["sources"]} == {"TECHNICAL", "NEWS"}
    assert first["sources"][1]["url"] == "https://example.com/2330"

    profile_response = client.post(
        "/api/v1/risk/assess",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "answers": {
                "experience_years": 1,
                "loss_tolerance": 1,
                "investment_goal": 1,
                "market_drop_reaction": 1,
                "investment_horizon": 1,
            },
            "target_return_pct": 8,
            "max_drawdown_pct": 5,
        },
    )
    assert profile_response.status_code == 200
    profile_result = client.post(
        "/api/v1/advisory/daily-recommendations",
        headers={"Authorization": f"Bearer {token}"},
        json={"investment_budget": 90000},
    )
    assert profile_result.status_code == 200, profile_result.text
    profile_body = profile_result.json()
    assert profile_body["user_risk_type"] == "保守型投資者"
    assert Decimal(profile_body["recommendations"][0]["target_sell_price"]) == Decimal("107.46")


def test_recommendation_rejects_unknown_source_id() -> None:
    candidate = ScreenerCandidate(
        symbol="2330", name="台積電", current_price=100, ma5=99, ma20=98, ma60=95,
        volatility_20d_pct=8, trend_score=80, data_date="2026-11-16",
        data_source="Mock", is_demo_data=False,
    )
    choice = RecommendationChoice(
        symbol="2330", reasoning="根據可查證的均線與趨勢資料，符合本次設定的觀察條件。",
        source_ids=["S999"],
    )
    technical = SourceReference(
        source_type="TECHNICAL", title="MA 技術指標",
        detail="MA5 99、MA20 98、MA60 95。", url="",
        published_at=datetime(2026, 11, 16),
    )

    with pytest.raises(daily_recommender_agent.RecommendationUnavailableError, match="來源編號"):
        daily_recommender_agent._build_recommendation(
            candidate, choice, [technical], Decimal(90000), Decimal(10), Decimal(5)
        )
