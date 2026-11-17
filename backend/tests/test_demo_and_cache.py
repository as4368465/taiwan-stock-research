from collections.abc import Iterator
from datetime import datetime, timedelta

import pandas as pd
import pytest
from app.main import create_app
from app.services import market_service, portfolio_service
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


def test_demo_login_returns_jwt_and_default_portfolio(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_analysis(symbol: str) -> dict:
        close = 1200 if symbol == "2330" else 160
        return {
            "name": "台積電" if symbol == "2330" else "鴻海",
            "data_source": "測試行情 Provider",
            "data": [{"date": "2026-11-17", "close": close}],
        }

    monkeypatch.setattr(portfolio_service, "get_stock_analysis", fake_analysis)

    login_response = client.post("/api/v1/auth/demo-login")

    assert login_response.status_code == 200, login_response.text
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    current_user = client.get("/api/v1/auth/me", headers=headers)
    holdings = client.get("/api/v1/portfolio", headers=headers)
    quota = client.get("/api/v1/advisory/quota", headers=headers)

    assert current_user.status_code == 200
    assert current_user.json()["email"] == "demo@quantguard.tw"
    assert current_user.json()["risk_type"] == "MODERATE"
    assert holdings.status_code == 200
    assert {item["stock_symbol"] for item in holdings.json()} == {"2330", "2317"}
    assert quota.status_code == 200
    assert quota.json()["user_used"] == 0


def test_stock_analysis_cache_avoids_duplicate_provider_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_service._market_cache.clear()
    calls = {"provider": 0, "daily_prices": 0}

    class FakeProvider:
        def get_daily_prices(self, _symbol: str) -> pd.DataFrame:
            calls["daily_prices"] += 1
            dates = pd.date_range("2026-10-01", periods=60, freq="B")
            return pd.DataFrame(
                {
                    "date": dates,
                    "open": range(100, 160),
                    "high": range(101, 161),
                    "low": range(99, 159),
                    "close": range(100, 160),
                    "volume": [1000] * 60,
                }
            )

        def get_stock_name(self, _symbol: str) -> str:
            return "測試股票"

    provider = FakeProvider()
    timestamps = iter((
        "2026-11-17T10:00:00+08:00",
        "2026-11-17T10:00:01+08:00",
    ))

    def get_provider():
        calls["provider"] += 1
        return provider, "測試資料來源", False

    monkeypatch.setattr(market_service, "get_provider", get_provider)
    monkeypatch.setattr(market_service, "_current_time_taipei", lambda: next(timestamps))

    first = market_service.get_stock_analysis("2330")
    second = market_service.get_stock_analysis("2330")

    assert calls == {"provider": 1, "daily_prices": 1}
    assert first["data"] == second["data"]
    assert first["updated_at"] == second["updated_at"]
    assert datetime.fromisoformat(first["updated_at"]).utcoffset() == timedelta(hours=8)

    refreshed = market_service.get_stock_analysis("2330", force_refresh=True)
    assert calls == {"provider": 2, "daily_prices": 2}
    assert refreshed["updated_at"] != first["updated_at"]
    market_service._market_cache.clear()
