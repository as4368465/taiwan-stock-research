from collections.abc import Iterator

import pandas as pd
import pytest
from app.agents import daily_recommender_agent
from app.agents.recommendation_graph import build_recommendation_graph
from app.main import create_app
from app.schemas.recommendation import (
    DailyRecommendationDraft,
    RecommendationAuditResult,
    RecommendationChoice,
)
from app.services.technical_indicators import calculate_technical_indicators
from fastapi.testclient import TestClient
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


def test_indicators_calculate_rsi_macd_and_latest_candle() -> None:
    dates = pd.date_range("2026-01-01", periods=40, freq="B")
    closes = [100 + day for day in range(40)]
    rows = [
        {
            "date": date.date().isoformat(),
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1000,
        }
        for date, close in zip(dates, closes, strict=True)
    ]
    # 末日紅 K 實體佔區間 75%，且突破前高並放量，應辨識成帶量長紅突破。
    rows[-1].update(open=134, high=144, low=132, close=142, volume=3000)

    result = calculate_technical_indicators(pd.DataFrame(rows))

    assert result.rsi14 == 100
    assert result.rsi_signal == "超買"
    assert result.macd_dif is not None and result.macd_dif > 0
    assert result.macd_histogram is not None and result.macd_histogram > 0
    assert float(result.volume_ratio) == pytest.approx(2.14, abs=0.01)
    assert result.candles[-1].candle_color == "紅K"
    assert result.candles[-1].pattern == "帶量長紅突破"
    assert result.candles[-1].date == rows[-1]["date"]


def test_glossary_search_and_category_filter(client: TestClient) -> None:
    search = client.get("/api/v1/glossary", params={"q": "RSI"})
    assert search.status_code == 200
    assert any(
        item["term"] == "RSI 相對強弱指標"
        for item in search.json()["terms"]
    )

    category = client.get(
        "/api/v1/glossary", params={"category": "技術指標"}
    )
    assert category.status_code == 200
    assert len(category.json()["terms"]) >= 5
    assert all(
        item["category"] == "技術指標" for item in category.json()["terms"]
    )


def test_langgraph_retries_after_audit_feedback_then_approves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"analyst": 0, "auditor": 0}
    draft = DailyRecommendationDraft(
        selections=[
            RecommendationChoice(
                symbol=f"233{index}",
                reasoning="此標的依據候選資料與技術來源進行評估，仍需持續觀察風險。",
                source_ids=["S1"],
            )
            for index in range(3)
        ]
    )

    def fake_llm(context: dict) -> DailyRecommendationDraft:
        calls["analyst"] += 1
        if calls["analyst"] == 2:
            assert "修正停損幅度" in context["前次風控審查意見"]
        return draft

    def fake_audit(_draft, _data) -> RecommendationAuditResult:
        calls["auditor"] += 1
        if calls["auditor"] == 1:
            return RecommendationAuditResult(
                approved=False, feedback="修正停損幅度", note="第一次審查未通過"
            )
        return RecommendationAuditResult(
            approved=True, feedback="", note="停損與來源均符合限制"
        )

    monkeypatch.setattr(daily_recommender_agent, "_generate_with_openai", fake_llm)
    monkeypatch.setattr(daily_recommender_agent, "_audit_recommendations", fake_audit)

    graph = build_recommendation_graph(
        lambda context, feedback: daily_recommender_agent._generate_with_openai(
            {**context, **({"前次風控審查意見": feedback} if feedback else {})}
        ),
        lambda current_draft, data: daily_recommender_agent._audit_recommendations(
            current_draft, data
        ),
    )
    result = graph.invoke({"context": {"候選": []}, "audit_data": {}, "retry_count": 0})

    assert calls == {"analyst": 2, "auditor": 2}
    assert result["retry_count"] == 1
    assert result["audit_approved"] is True
    assert result["audit_note"] == "停損與來源均符合限制"
