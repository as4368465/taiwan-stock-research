import json
import re
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

import openai
import pytest
from app.agents import sell_advisor_agent
from app.core.enums import RiskType
from app.core.security import create_access_token
from app.db.models import PortfolioItem, RiskProfile
from app.main import create_app
from app.schemas.advisory import SellAction, SellDiagnosisDraft
from app.services import portfolio_service
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


def register_and_login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "safe-password-123", "full_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    return create_access_token(str(response.json()["id"]))


def fake_analysis(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": "台積電",
        "data_source": "測試行情來源",
        "data": [
            {"date": "2026-11-13", "close": 100, "ma5": 98, "ma20": 96, "ma60": 94},
            {"date": "2026-11-16", "close": 110, "ma5": 101, "ma20": 97, "ma60": 95},
        ],
    }


def test_portfolio_create_read_update_and_decimal_pnl(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(portfolio_service, "get_stock_analysis", fake_analysis)
    headers = {"Authorization": f"Bearer {register_and_login(client, 'owner@example.com')}"}

    created = client.post(
        "/api/v1/portfolio",
        headers=headers,
        json={"stock_symbol": "2330", "average_cost": "100.25", "shares": 10},
    )
    item_id = created.json()["id"]
    listed = client.get("/api/v1/portfolio", headers=headers)
    updated = client.put(
        f"/api/v1/portfolio/{item_id}",
        headers=headers,
        json={"average_cost": "105.00", "shares": 20},
    )
    deleted = client.delete(f"/api/v1/portfolio/{item_id}", headers=headers)

    assert created.status_code == 201
    assert created.json()["stock_name"] == "台積電"
    assert listed.status_code == 200
    assert Decimal(listed.json()[0]["current_price"]) == Decimal(110)
    assert Decimal(listed.json()[0]["market_value"]) == Decimal("1100.00")
    assert Decimal(listed.json()[0]["unrealized_pnl"]) == Decimal("97.50")
    assert Decimal(listed.json()[0]["unrealized_return_pct"]) == Decimal("9.73")
    assert updated.status_code == 200
    assert updated.json()["shares"] == 20
    assert Decimal(updated.json()["unrealized_pnl"]) == Decimal("100.00")
    assert deleted.status_code == 204
    assert client.get("/api/v1/portfolio", headers=headers).json() == []


def test_user_cannot_delete_or_diagnose_another_users_item(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(portfolio_service, "get_stock_analysis", fake_analysis)
    token_a = register_and_login(client, "user-a@example.com")
    token_b = register_and_login(client, "user-b@example.com")
    item = client.post(
        "/api/v1/portfolio",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"stock_symbol": "2330", "average_cost": 100, "shares": 1},
    ).json()

    delete_response = client.delete(
        f"/api/v1/portfolio/{item['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    diagnosis_response = client.post(
        f"/api/v1/advisory/sell-diagnosis/{item['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    owner_items = client.get(
        "/api/v1/portfolio", headers={"Authorization": f"Bearer {token_b}"}
    ).json()

    assert delete_response.status_code == 404
    assert diagnosis_response.status_code == 404
    assert len(owner_items) == 1


def test_sell_diagnosis_returns_schema_and_grounded_sources(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(portfolio_service, "get_stock_analysis", fake_analysis)
    monkeypatch.setattr(sell_advisor_agent, "get_stock_analysis", fake_analysis)
    monkeypatch.setattr(
        sell_advisor_agent,
        "get_stock_news",
        lambda symbol, limit: {
            "news": [{
                "title": "台積電測試新聞",
                "summary": "測試摘要來自新聞 Provider。",
                "url": "https://example.com/news/2330",
                "published_at": "2026-11-16T09:00:00",
            }],
        },
    )
    monkeypatch.setattr(sell_advisor_agent.settings, "openai_api_key", SecretStr("test-key"))
    monkeypatch.setattr(
        sell_advisor_agent,
        "get_market_overview",
        lambda: {
            "data": [{"time": "09:00", "value": 22000}],
            "session_open": 21900,
            "latest_value": 22000,
            "latest_data_date": "2026-11-16",
            "data_source": "測試大盤來源",
        },
    )
    monkeypatch.setattr(
        sell_advisor_agent,
        "get_industry_peers",
        lambda symbol, limit: [{"stock_id": "2454", "stock_name": "聯發科"}],
    )

    def analysis_with_peer(symbol: str) -> dict:
        if symbol == "2454":
            return {
                "symbol": symbol,
                "name": "聯發科",
                "data": [
                    {"date": "2026-11-13", "close": 100, "ma5": 98, "ma20": 96, "ma60": 94},
                    {"date": "2026-11-16", "close": 120, "ma5": 101, "ma20": 97, "ma60": 95},
                ],
            }
        return fake_analysis(symbol)

    monkeypatch.setattr(sell_advisor_agent, "get_stock_analysis", analysis_with_peer)

    def fake_llm(context: dict, expected_action) -> SellDiagnosisDraft:
        assert context["同產業股票相對表現"][0]["股票"] == "聯發科（2454）"
        citation_ids = [
            source["source_id"] for source in context["sources"]
            if source["source_type"] in {"NEWS", "MARKET", "INDUSTRY"}
        ]
        return SellDiagnosisDraft(
            action=expected_action,
            confidence_level="MEDIUM",
            reasoning="目前回報不錯，但需要更多資料確認風險與公司近況。ドール企業。",
            source_ids=[context["sources"][0]["source_id"], *citation_ids],
        )

    monkeypatch.setattr(sell_advisor_agent, "_generate_with_openai", fake_llm)
    token = register_and_login(client, "advisor@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item = client.post(
        "/api/v1/portfolio",
        headers=headers,
        json={"stock_symbol": "2330", "average_cost": 100, "shares": 10},
    ).json()

    response = client.post(
        f"/api/v1/advisory/sell-diagnosis/{item['id']}", headers=headers
    )
    body = response.json()

    assert response.status_code == 200, body
    assert body["action"] == "HOLD"
    assert Decimal(str(body["suggested_sell_price_min"])) < Decimal(
        str(body["suggested_sell_price_max"])
    )
    assert body["confidence_level"] == "LOW"
    assert not re.search(r"[\u3040-\u30ff\u31f0-\u31ff]", body["reasoning"])
    assert "公司近況線索" in body["reasoning"]
    assert "聯發科（2454）近五日 20.00%" in body["reasoning"]
    assert "不能單獨證明資金輪動" in body["reasoning"]
    assert "結合大盤背景" in body["reasoning"]
    assert any(source["url"] == "https://example.com/news/2330" for source in body["sources"])
    assert any(source["source_type"] == "MARKET" for source in body["sources"])
    assert any(source["source_type"] == "INDUSTRY" for source in body["sources"])
    assert body["disclaimer"]


def test_sell_diagnosis_explains_missing_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(portfolio_service, "get_stock_analysis", fake_analysis)
    monkeypatch.setattr(sell_advisor_agent.settings, "openai_api_key", None)
    token = register_and_login(client, "no-key@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item = client.post(
        "/api/v1/portfolio",
        headers=headers,
        json={"stock_symbol": "2330", "average_cost": 100, "shares": 1},
    ).json()

    response = client.post(
        f"/api/v1/advisory/sell-diagnosis/{item['id']}", headers=headers
    )

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_openai_sdk_request_uses_strict_pydantic_json_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sell_advisor_agent.settings, "openai_api_key", SecretStr("test-key"))
    captured: dict = {}

    def fake_sdk_post(_client, path: str, *, cast_to, body: dict):
        captured.update(path=path, cast_to=cast_to, body=body)
        return {"choices": [{"message": {"content": json.dumps({
            "action": "HOLD",
            "confidence_level": "LOW",
            "reasoning": "目前證據不足，僅能依據已提供的行情資料持續觀察。",
            "source_ids": ["S1"],
        })}}]}

    monkeypatch.setattr(openai.OpenAI, "post", fake_sdk_post)
    draft = sell_advisor_agent._generate_with_openai({"sources": []}, sell_advisor_agent.SellAction.HOLD)

    assert captured["path"] == "/chat/completions"
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["strict"] is True
    assert draft.action.value == "HOLD"


@pytest.mark.parametrize(
    ("risk_type", "price", "target", "drawdown", "expected"),
    [
        (RiskType.CONSERVATIVE, "110", "8", "5", SellAction.TAKE_PROFIT),
        (RiskType.AGGRESSIVE, "110", "20", "20", SellAction.HOLD),
        (RiskType.MODERATE, "94", "12", "5", SellAction.STOP_LOSS),
    ],
)
def test_deterministic_sell_rule_uses_risk_profile_and_trend(
    risk_type: RiskType,
    price: str,
    target: str,
    drawdown: str,
    expected: SellAction,
) -> None:
    item = PortfolioItem(average_cost=Decimal(100))
    profile = RiskProfile(
        risk_type=risk_type,
        target_return_pct=Decimal(target),
        max_drawdown_pct=Decimal(drawdown),
    )
    technical = {"latest": {"ma5": 105, "ma20": 100, "ma60": 95}}

    action, _price_min, _price_max, _pnl_pct = sell_advisor_agent._deterministic_decision(
        item, Decimal(price), technical, profile
    )

    assert action is expected


def test_industry_comparison_uses_same_date_peer_returns_and_labels_sample_limit() -> None:
    peer_analysis = {
        "name": "聯發科",
        "data": [
            {"date": "2026-11-13", "close": 100},
            {"date": "2026-11-16", "close": 110},
        ],
    }

    sources, context = sell_advisor_agent._industry_sources(
        [{"stock_id": "2454", "stock_name": "聯發科", "analysis": peer_analysis}],
        Decimal(-5),
        "2026-11-16",
    )

    assert len(sources) == 1
    assert sources[0].source_type.value == "INDUSTRY"
    assert "近五個交易日報酬率 10.00%" in sources[0].detail
    assert context[-1]["比較摘要"].startswith("同產業對照樣本 1 檔中 1 檔")
    assert "不能單獨證明資金輪動" in context[-1]["比較摘要"]


def test_industry_comparison_ignores_different_market_dates() -> None:
    sources, context = sell_advisor_agent._industry_sources(
        [{"stock_id": "2454", "analysis": {"data": [
            {"date": "2026-11-12", "close": 100},
            {"date": "2026-11-13", "close": 110},
        ]}}],
        Decimal(-5),
        "2026-11-16",
    )

    assert sources == []
    assert context == []


def test_fallback_does_not_repeat_japanese_characters_from_news() -> None:
    source = sell_advisor_agent.SourceReference(
        source_type="NEWS",
        title="会社の新しい発表",
        detail="投資家の信頼を損なう可能性",
        url="https://example.com/news",
        published_at=datetime(2026, 11, 16),
    )

    excerpt = sell_advisor_agent._safe_news_excerpt(source)

    assert excerpt == "新聞來源含非預期外文字，請點擊參考來源查閱原文"
    assert not re.search(r"[\u3040-\u30ff\u31f0-\u31ff]", excerpt)
