"""
Python port of technical indicators from client/lib/candleAnalysis.ts.

All functions work with candle dicts: {"time": int, "open": float, "high": float,
"low": float, "close": float, "volume": int}.

Python 3.9 compatible — uses List[float] not list[float].
"""

import math


def calculate_ema(closes, period):
    # type: (List[float], int) -> List[float]
    """Exponential Moving Average. Returns list same length as closes (NaN-padded)."""
    n = len(closes)
    ema = [float("nan")] * n
    if n < period:
        return ema

    # Seed with SMA of first `period` values
    s = 0.0
    for i in range(period):
        s += closes[i]
    ema[period - 1] = s / period

    k = 2.0 / (period + 1)
    for i in range(period, n):
        ema[i] = closes[i] * k + ema[i - 1] * (1 - k)
    return ema


def calculate_rsi(candles, period=14):
    # type: (List[dict], int) -> Dict[str, Any]
    """RSI with Wilder's smoothing. Returns {current, zone, values}."""
    closes = [c["close"] for c in candles]
    n = len(closes)
    values = [float("nan")] * n

    if n < period + 1:
        return {"current": 50.0, "zone": "NEUTRAL", "values": values}

    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            avg_gain += diff
        else:
            avg_loss += abs(diff)
    avg_gain /= period
    avg_loss /= period

    rs0 = 100.0 if avg_loss == 0 else avg_gain / avg_loss
    values[period] = 100.0 - 100.0 / (1.0 + rs0)

    for i in range(period + 1, n):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = abs(diff) if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = 100.0 if avg_loss == 0 else avg_gain / avg_loss
        values[i] = 100.0 - 100.0 / (1.0 + rs)

    current = values[-1] if not math.isnan(values[-1]) else 50.0
    if current < 30:
        zone = "OVERSOLD"
    elif current > 65:
        zone = "OVERBOUGHT"
    else:
        zone = "NEUTRAL"

    return {
        "current": round(current, 1),
        "zone": zone,
        "values": values,
    }


def calculate_atr(candles, period=14):
    # type: (List[dict], int) -> float
    """Average True Range with Wilder's smoothing."""
    if len(candles) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Seed with SMA
    atr = sum(true_ranges[:period]) / period

    # Wilder's smoothing
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period

    return round(atr, 2)


def calculate_vwap(candles, ltp=None):
    # type: (List[dict], Optional[float]) -> Dict[str, Any]
    """Session-anchored VWAP. Returns {vwap, above_vwap}."""
    if not candles:
        return {"vwap": 0.0, "above_vwap": False}

    # IST session start = 9:15 AM IST = 03:45 UTC
    IST_START_UTC_H = 3
    IST_START_UTC_M = 45

    # Find the latest session start boundary
    session_start_idx = 0
    for i in range(len(candles) - 1, -1, -1):
        ts = candles[i]["time"]
        import datetime
        d = datetime.datetime.utcfromtimestamp(ts)
        utc_h = d.hour
        utc_m = d.minute

        if utc_h == IST_START_UTC_H and IST_START_UTC_M <= utc_m < IST_START_UTC_M + 5:
            session_start_idx = i
            break
        if i > 0:
            prev_d = datetime.datetime.utcfromtimestamp(candles[i - 1]["time"])
            if d.day != prev_d.day:
                session_start_idx = i
                break

    cum_tpv = 0.0
    cum_vol = 0
    for i in range(session_start_idx, len(candles)):
        c = candles[i]
        typical = (c["high"] + c["low"] + c["close"]) / 3.0
        cum_tpv += typical * c["volume"]
        cum_vol += c["volume"]

    vwap = round(cum_tpv / cum_vol, 2) if cum_vol > 0 else 0.0
    current_price = ltp if ltp is not None else candles[-1]["close"]

    return {"vwap": vwap, "above_vwap": current_price > vwap}


def analyze_volume(candles, lookback=20):
    # type: (List[dict], int) -> Dict[str, Any]
    """Volume analysis. Returns {current, average, ratio, confirmed}."""
    if len(candles) < 2:
        return {"current": 0, "average": 0, "ratio": 0.0, "confirmed": False}

    current = candles[-1]["volume"]
    hist = candles[-(lookback + 1):-1]
    if hist:
        average = sum(c["volume"] for c in hist) / len(hist)
    else:
        average = float(current)

    ratio = round(current / average, 1) if average > 0 else 0.0

    return {
        "current": current,
        "average": round(average),
        "ratio": ratio,
        "confirmed": ratio >= 2.0,
    }
