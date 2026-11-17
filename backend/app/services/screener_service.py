"""以固定規則從核心觀察池篩選候選股；本層不呼叫 LLM。"""

from concurrent.futures import ThreadPoolExecutor
from decimal import ROUND_HALF_UP, Decimal
from math import sqrt

import pandas as pd

from app.core.enums import RiskType
from app.schemas.recommendation import ScreenerCandidate
from app.services.market_service import get_stock_analysis

CORE_WATCHLIST = (
    ("2330", "台積電"), ("2317", "鴻海"), ("2454", "聯發科"),
    ("2881", "富邦金"), ("2882", "國泰金"), ("2412", "中華電"),
    ("0050", "元大台灣50"), ("0056", "元大高股息"),
    ("2382", "廣達"), ("3231", "緯創"),
)
CENT = Decimal("0.01")


def _score_trend(
    close: Decimal,
    ma5: Decimal,
    ma20: Decimal,
    ma60: Decimal,
    volatility_pct: Decimal,
    risk_type: RiskType,
) -> int:
    score = 0
    if ma5 > ma20 > ma60:
        score += 40
    elif ma5 > ma20:
        score += 25
    elif ma20 > ma60:
        score += 15
    if close > ma20:
        score += 15
    if close > ma60:
        score += 15

    if risk_type is RiskType.CONSERVATIVE:
        score += max(0, 30 - int(volatility_pct * 2))
    elif risk_type is RiskType.AGGRESSIVE:
        score += min(30, int(volatility_pct * 2))
    else:
        score += max(0, 30 - int(abs(volatility_pct - Decimal(12)) * 2))
    return min(100, score)


def _candidate(
    symbol: str,
    fallback_name: str,
    analysis: dict,
    investment_budget: Decimal,
    risk_type: RiskType,
) -> ScreenerCandidate | None:
    rows = analysis.get("data", [])
    if len(rows) < 60:
        return None
    latest = rows[-1]
    if not latest.get("close") or any(latest.get(key) is None for key in ("ma5", "ma20", "ma60")):
        return None

    close = Decimal(str(latest["close"]))
    if close > investment_budget:
        return None
    returns = pd.Series([float(row["close"]) for row in rows[-21:]]).pct_change().dropna()
    if returns.empty:
        return None
    volatility = Decimal(str(returns.std(ddof=1) * sqrt(20) * 100)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    ma5, ma20, ma60 = (Decimal(str(latest[key])) for key in ("ma5", "ma20", "ma60"))
    source = analysis.get("data_source", "行情 Provider")
    demo = analysis.get("is_demo_data", False)
    return ScreenerCandidate(
        symbol=symbol,
        name=analysis.get("name") or fallback_name,
        current_price=close,
        ma5=ma5,
        ma20=ma20,
        ma60=ma60,
        volatility_20d_pct=volatility,
        trend_score=_score_trend(close, ma5, ma20, ma60, volatility, risk_type),
        data_date=str(latest["date"]),
        data_source=str(source),
        is_demo_data=bool(demo),
    )


def screen_candidates(
    investment_budget: Decimal,
    risk_type: RiskType,
    limit: int = 5,
) -> tuple[list[ScreenerCandidate], str]:
    """掃描固定觀察池，排除資料不足或單股價格超預算者後回傳前 N 名。"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            symbol: executor.submit(get_stock_analysis, symbol)
            for symbol, _ in CORE_WATCHLIST
        }
        results = []
        for symbol, name in CORE_WATCHLIST:
            try:
                analysis = futures[symbol].result()
            except (RuntimeError, ValueError, KeyError, TypeError):
                continue
            candidate = _candidate(symbol, name, analysis, investment_budget, risk_type)
            if candidate:
                results.append(candidate)

    results.sort(key=lambda item: (-item.trend_score, item.volatility_20d_pct, item.symbol))
    shortlisted = results[:limit]
    if results:
        above_ma20 = sum(item.current_price > item.ma20 for item in results)
        market_summary = (
            f"核心觀察池中有 {len(results)} 檔符合預算與 60 日資料條件，"
            f"其中 {above_ma20} 檔收盤價高於 MA20。這是有限觀察池的技術面概況，"
            "不代表整體市場廣度或資金流向。"
        )
    else:
        market_summary = "目前觀察池沒有足夠且符合預算的行情資料，無法產生市場概況。"
    return shortlisted, market_summary
