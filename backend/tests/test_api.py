from app.api.v1 import news as news_router
from app.main import app
from app.providers import news_service as news_provider
from app.providers.data_provider import SampleDataProvider
from app.services import market_service
from app.services import news_service as news_service_layer
from fastapi.testclient import TestClient

client = TestClient(app)


def test_stock_analysis_api_keeps_existing_response(monkeypatch) -> None:
    monkeypatch.setattr(
        market_service,
        "get_provider",
        lambda: (SampleDataProvider(), "本地示範資料", True),
    )

    response = client.get("/api/stocks/2330/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "2330"
    assert payload["name"] == "台積電（示範）"
    assert payload["data"]
    assert {"date", "close", "ma5", "ma20", "ma60"} <= payload["data"][-1].keys()


def test_news_api_keeps_pagination_and_utf8_response(monkeypatch) -> None:
    page = {
        "symbol": "2330",
        "data_source": "測試新聞來源",
        "news": [{
            "id": 1,
            "stock_id": "2330",
            "title": "台積電測試新聞",
            "url": "https://example.com/news/1",
            "source": "測試來源",
            "published_at": "2026-11-16T09:00:00",
            "summary": "新聞摘要",
        }],
        "next_cursor": "2026-11-16T09:00:00|1",
        "has_more": True,
        "oldest_available_date": "2025-11-16",
        "retention_days": 365,
    }
    monkeypatch.setattr(news_router, "get_stock_news", lambda *_args, **_kwargs: page)

    response = client.get("/api/stocks/2330/news?limit=10")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    payload = response.json()
    assert payload["news"][0]["title"] == "台積電測試新聞"
    assert payload["next_cursor"] == page["next_cursor"]
    assert payload["has_more"] is True


def test_news_api_rejects_invalid_stock_symbol() -> None:
    response = client.get("/api/stocks/not-a-stock/news")

    assert response.status_code == 400


def test_news_api_uses_local_cache_in_sample_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        news_service_layer,
        "get_provider",
        lambda: (SampleDataProvider(), "本地示範資料", True),
    )
    monkeypatch.setattr(news_provider, "DB_PATH", tmp_path / "isolated-news.sqlite3")

    response = client.get("/api/stocks/2330/news")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "2330"
    assert payload["news"] == []
    assert payload["has_more"] is False
    assert payload["retention_days"] == 365
