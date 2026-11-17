"""可替換的日線資料來源：本地示範資料與 FinMind REST API。"""

import json
import re
from datetime import date, timedelta
from pathlib import Path
from time import monotonic
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from app.core.config import settings


class StockDataProvider(Protocol):
    """不同資料來源共用的介面，API 不必綁定特定供應商。"""

    def get_daily_prices(self, symbol: str) -> pd.DataFrame:
        ...

    def search_stocks(self, query: str) -> list[dict[str, str]]:
        ...

    def get_stock_name(self, symbol: str) -> str | None:
        ...

    def get_industry_peers(self, symbol: str, limit: int = 3) -> list[dict[str, str]]:
        ...

    def get_news_for_date(self, symbol: str, news_date: date) -> list[dict]:
        ...

    def get_market_index(self) -> pd.DataFrame:
        ...


class SampleDataProvider:
    def get_daily_prices(self, symbol: str) -> pd.DataFrame:
        data_dir = Path(__file__).resolve().parents[2] / "data"
        file_path = data_dir / f"{symbol}.csv"
        if not file_path.is_file():
            raise ValueError(f"沒有 {symbol} 的本地示範資料")
        return pd.read_csv(file_path, parse_dates=["date"])

    def search_stocks(self, query: str) -> list[dict[str, str]]:
        demo_stocks = [{"stock_id": "2330", "stock_name": "台積電"}]
        normalized_query = query.casefold()
        return [
            stock for stock in demo_stocks
            if normalized_query in stock["stock_id"].casefold()
            or normalized_query in stock["stock_name"].casefold()
        ]

    def get_stock_name(self, symbol: str) -> str | None:
        return "台積電（示範）" if symbol == "2330" else None

    def get_industry_peers(self, symbol: str, limit: int = 3) -> list[dict[str, str]]:
        # 示範模式沒有股票分類資料，避免拿虛構同業做比較。
        return []

    def get_news_for_date(self, symbol: str, news_date: date) -> list[dict]:
        # 示範資料夾沒有新聞，因此離線模式回傳空清單。
        return []

    def get_market_index(self) -> pd.DataFrame:
        # 本地樣本目前沒有大盤指數資料，回傳空表讓 API 顯示清楚的提示。
        return pd.DataFrame(columns=["time", "value"])


_stock_info_cache: list[dict[str, str]] = []
_stock_info_cached_at = 0.0
_stock_info_cache_seconds = 24 * 60 * 60


def request_finmind_data(parameters: dict[str, str]) -> list[dict]:
    query = urlencode(parameters)
    request = Request(
        f"https://api.finmindtrade.com/api/v4/data?{query}",
        headers={"User-Agent": "TaiwanStockResearchLearningProject/0.1"},
    )

    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"FinMind 回傳 HTTP {error.code}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError("連不到 FinMind，請稍後再試") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("FinMind 回傳的資料格式無法讀取") from error

    status = payload.get("status")
    if status is not None and str(status).lower() not in {"200", "success"}:
        raise RuntimeError(payload.get("msg", "FinMind 查詢失敗"))

    records = payload.get("data", [])
    if not isinstance(records, list):
        raise RuntimeError("FinMind 回傳的資料格式不正確")  # noqa: TRY004
    return records


class FinMindDataProvider:
    """透過 FinMind 的 REST API 取得個股歷史日成交資料，不需 SDK。"""

    def get_daily_prices(self, symbol: str) -> pd.DataFrame:
        # 約一年日曆日通常足以包含 60 個以上交易日，並保留一些休市緩衝。
        start_date = (date.today() - timedelta(days=365)).isoformat()
        records = request_finmind_data({
            "dataset": "TaiwanStockPrice",
            "data_id": symbol,
            "start_date": start_date,
        })
        if not records:
            raise ValueError(f"FinMind 沒有 {symbol} 的歷史日線資料")

        # FinMind 欄位名稱轉為本專案自己的欄位名稱，避免前端被供應商格式綁定。
        frame = pd.DataFrame(records).rename(columns={
            "Trading_Volume": "volume",
            "max": "high",
            "min": "low",
        })
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise RuntimeError(f"FinMind 回傳資料缺少欄位：{', '.join(missing)}")

        frame = frame[required].copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for column in required[1:]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=required).sort_values("date").reset_index(drop=True)
        if frame.empty:
            raise ValueError(f"FinMind 沒有可用的 {symbol} 歷史日線資料")
        return frame

    def get_market_index(self) -> pd.DataFrame:
        """取得最近一個有資料交易日的加權指數盤中走勢。"""
        # FinMind 此資料集一次只回傳一天；週末或休市時往前找最近交易日。
        for days_ago in range(10):
            query_date = date.today() - timedelta(days=days_ago)
            records = request_finmind_data({
                "dataset": "TaiwanVariousIndicators5Seconds",
                "start_date": query_date.isoformat(),
            })
            if not records:
                continue

            frame = pd.DataFrame(records)
            if "date" not in frame.columns or "TAIEX" not in frame.columns:
                raise RuntimeError("FinMind 回傳的大盤指數欄位格式不正確")
            frame["time"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["value"] = pd.to_numeric(frame["TAIEX"], errors="coerce")
            frame = frame.dropna(subset=["time", "value"]).sort_values("time")
            if frame.empty:
                continue

            # 原資料每 5 秒一筆；畫面保留整分鐘資料，減少圖表點數但仍看得出盤中變化。
            frame = frame[frame["time"].dt.second == 0].copy()
            if frame.empty:
                continue
            frame.attrs["market_date"] = frame["time"].iloc[-1].strftime("%Y-%m-%d")
            frame["time"] = frame["time"].dt.strftime("%H:%M")
            return frame[["time", "value"]].reset_index(drop=True)

        raise ValueError("近 10 天找不到加權指數資料，請稍後再試")

    def _get_stock_info(self) -> list[dict[str, str]]:
        global _stock_info_cache, _stock_info_cached_at
        if _stock_info_cache and monotonic() - _stock_info_cached_at < _stock_info_cache_seconds:
            return _stock_info_cache

        records = request_finmind_data({"dataset": "TaiwanStockInfo"})
        # TaiwanStockInfo 可能同一股票有不同日期的資料列；保留最新分類資料。
        latest_by_id: dict[str, dict[str, str]] = {}
        for row in records:
            if not row.get("stock_id") or not row.get("stock_name"):
                continue
            stock_id = str(row["stock_id"])
            current = latest_by_id.get(stock_id)
            if current is None or str(row.get("date", "")) >= current.get("date", ""):
                latest_by_id[stock_id] = {
                    "stock_id": stock_id,
                    "stock_name": str(row["stock_name"]),
                    "industry_category": str(row.get("industry_category") or ""),
                    "type": str(row.get("type") or ""),
                    "date": str(row.get("date") or ""),
                }
        _stock_info_cache = list(latest_by_id.values())
        _stock_info_cached_at = monotonic()
        return _stock_info_cache

    def search_stocks(self, query: str) -> list[dict[str, str]]:
        normalized_query = query.strip().casefold()
        matches = [
            stock for stock in self._get_stock_info()
            if normalized_query in stock["stock_id"].casefold()
            or normalized_query in stock["stock_name"].casefold()
        ]
        matches.sort(key=lambda stock: (
            stock["stock_id"].casefold() != normalized_query,
            stock["stock_name"].casefold() != normalized_query,
            not stock["stock_name"].casefold().startswith(normalized_query),
            stock["stock_id"],
        ))
        return matches[:12]

    def get_stock_name(self, symbol: str) -> str | None:
        return next(
            (stock["stock_name"] for stock in self._get_stock_info()
             if stock["stock_id"] == symbol),
            None,
        )

    def get_industry_peers(self, symbol: str, limit: int = 3) -> list[dict[str, str]]:
        stocks = self._get_stock_info()
        target = next((stock for stock in stocks if stock["stock_id"] == symbol), None)
        industry = target.get("industry_category", "") if target else ""
        if not industry:
            return []
        # 只取同產業、一般股票，限制數量以免診斷觸發大量行情請求。
        peers = [
            stock for stock in stocks
            if stock["stock_id"] != symbol
            and stock.get("industry_category") == industry
            and stock.get("type", "").casefold() in {"twse", "tpex", "上市", "上櫃", ""}
            and re.fullmatch(r"\d{4,6}", stock["stock_id"])
        ]
        peers.sort(key=lambda stock: stock["stock_id"])
        return peers[:max(0, limit)]

    def get_news_for_date(self, symbol: str, news_date: date) -> list[dict]:
        # FinMind 的 TaiwanStockNews 一次只能查一天，所以由 service 控制日期範圍。
        return request_finmind_data({
            "dataset": "TaiwanStockNews",
            "data_id": symbol,
            "start_date": news_date.isoformat(),
        })


def get_provider() -> tuple[StockDataProvider, str, bool]:
    provider_name = settings.data_provider.strip().lower()
    if provider_name == "sample":
        return SampleDataProvider(), "本地示範資料", True
    if provider_name == "finmind":
        return FinMindDataProvider(), "FinMind（台股歷史日線）", False
    raise ValueError("DATA_PROVIDER 只能設定為 finmind 或 sample")


def valid_symbol(symbol: str) -> bool:
    return re.fullmatch(r"\d{4,6}", symbol) is not None
