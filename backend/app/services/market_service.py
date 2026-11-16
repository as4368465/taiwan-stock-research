"""市場與個股分析商業邏輯；API router 不直接處理 DataFrame。"""


from app.providers.data_provider import get_provider, valid_symbol


def search_stocks(query: str) -> dict:
    provider, _, _ = get_provider()
    return {"query": query, "results": provider.search_stocks(query)}


def get_stock_analysis(symbol: str) -> dict:
    if not valid_symbol(symbol):
        raise ValueError("股票代號格式應為 4 到 6 位數字")

    provider, source, is_demo_data = get_provider()
    frame = provider.get_daily_prices(symbol).sort_values("date").reset_index(drop=True)
    stock_name = provider.get_stock_name(symbol) or symbol
    for window in (5, 20, 60):
        frame[f"ma{window}"] = frame["close"].rolling(window=window).mean()

    # 將 Pandas NaN 轉成 None，才能輸出為標準 JSON null。
    frame = frame.astype(object).where(frame.notna(), None)
    rows = frame.to_dict(orient="records")
    for row in rows:
        row["date"] = row["date"].strftime("%Y-%m-%d")

    return {
        "symbol": symbol,
        "name": stock_name,
        "is_demo_data": is_demo_data,
        "data_source": source,
        "latest_data_date": rows[-1]["date"] if rows else None,
        "is_realtime": False,
        "notice": "此為交易所盤後歷史日線，不是盤中即時行情；不構成投資建議。",
        "latest_close": rows[-1]["close"] if rows else None,
        "data": rows,
    }


def get_market_overview() -> dict:
    provider, source, is_demo_data = get_provider()
    frame = provider.get_market_index()
    if frame.empty:
        raise ValueError("目前的示範資料沒有大盤指數")

    rows = frame.to_dict(orient="records")
    values = [row["value"] for row in rows]
    return {
        "symbol": "TAIEX",
        "name": "加權指數",
        "is_demo_data": is_demo_data,
        "data_source": "FinMind TaiwanVariousIndicators5Seconds" if not is_demo_data else source,
        "latest_data_date": frame.attrs.get("market_date"),
        "latest_value": values[-1],
        "session_open": values[0],
        "session_high": max(values),
        "session_low": min(values),
        "data": rows,
        "notice": "此為最近交易日盤中指數資料；來源更新時間可能延遲，不構成投資建議。",
    }
