"""以 Pandas 確定性計算 K 棒、量比、RSI 與 MACD，不使用 TA-Lib。"""

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from app.schemas.technical import CandleFeature, TechnicalIndicatorSnapshot

TWO_DECIMALS = Decimal("0.01")


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)


def _candle_feature(row: pd.Series, prior_high: float | None, volume_ratio: float | None) -> CandleFeature:
    opening, high, low, close = (float(row[key]) for key in ("open", "high", "low", "close"))
    full_range = max(high - low, 0.0)
    body = abs(close - opening)
    body_ratio = body / full_range * 100 if full_range else 0.0
    upper = (high - max(opening, close)) / full_range * 100 if full_range else 0.0
    lower = (min(opening, close) - low) / full_range * 100 if full_range else 0.0
    color = "紅K" if close > opening else "黑K" if close < opening else "十字" 

    if full_range and body_ratio <= 10:
        pattern = "十字星（觀察多空變化）"
    elif full_range and lower >= 45 and lower > body_ratio:
        pattern = "長下影線（觀察支撐）"
    elif full_range and upper >= 45 and upper > body_ratio:
        pattern = "長上影線（觀察壓力）"
    elif color == "紅K" and body_ratio >= 55:
        breakout = prior_high is not None and close > prior_high
        high_volume = volume_ratio is not None and volume_ratio >= 1.5
        if breakout and high_volume:
            pattern = "帶量長紅突破"
        elif high_volume:
            pattern = "帶量長紅"
        else:
            pattern = "長紅K"
    elif color == "黑K" and body_ratio >= 55:
        pattern = "長黑K"
    else:
        pattern = f"一般{color}"

    return CandleFeature(
        date=str(row["date"]),
        open=_decimal(opening),
        high=_decimal(high),
        low=_decimal(low),
        close=_decimal(close),
        body_ratio_pct=_decimal(body_ratio),
        upper_shadow_ratio_pct=_decimal(upper),
        lower_shadow_ratio_pct=_decimal(lower),
        candle_color=color,
        pattern=pattern,
    )


def calculate_technical_indicators(prices: pd.DataFrame) -> TechnicalIndicatorSnapshot:
    """分析最新 K 棒與近三日型態，並回傳最新量價動能指標。"""
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"計算技術特徵缺少必要欄位：{', '.join(sorted(missing))}")
    if len(prices) < 1:
        raise ValueError("至少需要一筆 OHLCV 行情才能計算技術特徵")

    frame = prices.copy()
    if "date" not in frame.columns:
        frame["date"] = frame.index.astype(str)
    frame = frame.sort_values("date").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close", "volume"])
    if frame.empty:
        raise ValueError("行情資料沒有可計算的 OHLCV 數值")

    volume_mean = frame["volume"].rolling(5, min_periods=1).mean().iloc[-1]
    current_volume = float(frame["volume"].iloc[-1])
    volume_ratio = current_volume / float(volume_mean) if volume_mean and np.isfinite(volume_mean) else None
    if volume_ratio is None:
        volume_signal = "資料不足"
    elif volume_ratio >= 1.5:
        volume_signal = "放量"
    elif volume_ratio <= 0.7:
        volume_signal = "量縮"
    else:
        volume_signal = "接近五日均量"

    candle_rows = []
    for position in range(max(0, len(frame) - 3), len(frame)):
        prior = frame["high"].iloc[max(0, position - 20):position]
        reference_high = float(prior.max()) if not prior.empty else None
        current_ratio = volume_ratio if position == len(frame) - 1 else None
        candle_rows.append(_candle_feature(frame.iloc[position], reference_high, current_ratio))

    close = frame["close"]
    changes = close.diff().dropna().to_numpy(dtype=float)
    if len(changes) < 14:
        rsi = None
        rsi_signal = "資料不足（至少需要 15 個收盤價）"
    else:
        gains = np.clip(changes, 0, None)
        losses = np.clip(-changes, 0, None)
        average_gain = float(gains[:14].mean())
        average_loss = float(losses[:14].mean())
        # Wilder RSI 先用 14 筆平均初始化，再逐筆以 1/14 平滑。
        for gain, loss in zip(gains[14:], losses[14:], strict=True):
            average_gain = (average_gain * 13 + gain) / 14
            average_loss = (average_loss * 13 + loss) / 14
        if average_loss == 0 and average_gain == 0:
            rsi = 50.0
        elif average_loss == 0:
            rsi = 100.0
        else:
            rsi = 100 - 100 / (1 + average_gain / average_loss)
        rsi_signal = "超買" if rsi > 70 else "超賣" if rsi < 30 else "中性"

    fast = close.ewm(span=12, min_periods=12, adjust=False).mean()
    slow = close.ewm(span=26, min_periods=26, adjust=False).mean()
    dif = fast - slow
    dea = dif.ewm(span=9, min_periods=9, adjust=False).mean()
    histogram = dif - dea
    if len(frame) < 34 or pd.isna(histogram.iloc[-1]):
        macd_values = (None, None, None)
        macd_signal = "資料不足（至少需要 34 個收盤價）"
    else:
        latest_hist = float(histogram.iloc[-1])
        previous_hist = float(histogram.iloc[-2])
        direction = "多方" if latest_hist >= 0 else "空方"
        trend = "增強" if latest_hist > previous_hist else "減弱" if latest_hist < previous_hist else "持平"
        macd_signal = f"{direction}{trend}"
        macd_values = (float(dif.iloc[-1]), float(dea.iloc[-1]), latest_hist)

    return TechnicalIndicatorSnapshot(
        latest_date=str(frame["date"].iloc[-1]),
        candles=candle_rows,
        volume_ratio=_decimal(volume_ratio) if volume_ratio is not None else None,
        volume_signal=volume_signal,
        rsi14=_decimal(float(rsi)) if rsi is not None and np.isfinite(rsi) else None,
        rsi_signal=rsi_signal,
        macd_dif=_decimal(macd_values[0]) if macd_values[0] is not None else None,
        macd_dea=_decimal(macd_values[1]) if macd_values[1] is not None else None,
        macd_histogram=_decimal(macd_values[2]) if macd_values[2] is not None else None,
        macd_signal=macd_signal,
    )


def technical_indicator_source(snapshot: TechnicalIndicatorSnapshot):
    """將計算後的指標轉成可在前端查證的技術來源。"""
    from app.schemas.advisory import SourceReference, SourceType

    latest_candle = snapshot.candles[-1]
    detail = (
        f"資料日 {snapshot.latest_date}；最新 K 棒：{latest_candle.pattern}，"
        f"實體比例 {latest_candle.body_ratio_pct}%，上影線 {latest_candle.upper_shadow_ratio_pct}%，"
        f"下影線 {latest_candle.lower_shadow_ratio_pct}%；量比 {snapshot.volume_ratio}x（{snapshot.volume_signal}）；"
        f"RSI14 {snapshot.rsi14}（{snapshot.rsi_signal}）；MACD DIF {snapshot.macd_dif}、"
        f"DEA {snapshot.macd_dea}、柱狀體 {snapshot.macd_histogram}（{snapshot.macd_signal}）。"
    )
    return SourceReference(
        source_type=SourceType.TECHNICAL,
        title="K 棒、量比、RSI14 與 MACD 技術快照",
        detail=detail[:1200],
        url="",
        published_at=pd.Timestamp(snapshot.latest_date).to_pydatetime(),
    )
