"""
Symbol detail helpers: historical candles, quote, exchange_token resolution.
"""

import time
from datetime import datetime, timedelta


def fetch_candles(groww, symbol: str, interval: str = "5minute", days: int = 5) -> list[dict]:
    """Fetch historical OHLCV candles for a trading symbol."""
    instrument = groww.get_instrument_by_exchange_and_trading_symbol("NSE", symbol)
    groww_symbol = instrument.get("groww_symbol") or instrument.get("symbol") or symbol

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    raw = groww.get_historical_candles(
        exchange="NSE",
        segment="CASH",
        groww_symbol=groww_symbol,
        start_time=start_str,
        end_time=end_str,
        candle_interval=interval,
    )

    candles = []
    data_list = raw if isinstance(raw, list) else raw.get("candles", raw.get("data", []))
    for c in data_list:
        if isinstance(c, dict):
            ts = c.get("timestamp") or c.get("time") or c.get("date", "")
            candles.append({
                "time": _to_unix(ts),
                "open": float(c.get("open") or 0),
                "high": float(c.get("high") or 0),
                "low": float(c.get("low") or 0),
                "close": float(c.get("close") or 0),
                "volume": int(c.get("volume") or 0),
            })
        elif isinstance(c, (list, tuple)) and len(c) >= 5:
            candles.append({
                "time": _to_unix(c[0]),
                "open": float(c[1] or 0),
                "high": float(c[2] or 0),
                "low": float(c[3] or 0),
                "close": float(c[4] or 0),
                "volume": int(c[5] or 0) if len(c) > 5 else 0,
            })
    candles.sort(key=lambda x: x["time"])
    return candles


def fetch_quote(groww, symbol: str) -> dict:
    """Fetch current quote for a trading symbol."""
    raw = groww.get_quote(trading_symbol=symbol, exchange="NSE", segment="CASH")

    if isinstance(raw, dict):
        ltp = float(raw.get("ltp", 0))
        prev_close = float(raw.get("prev_close", raw.get("previous_close", 0)))
        change = ltp - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "symbol": symbol,
            "ltp": ltp,
            "open": float(raw.get("open", 0)),
            "high": float(raw.get("high", 0)),
            "low": float(raw.get("low", 0)),
            "close": float(raw.get("close", ltp)),
            "prev_close": prev_close,
            "volume": int(raw.get("volume", 0)),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }

    return {"symbol": symbol, "ltp": 0, "open": 0, "high": 0, "low": 0,
            "close": 0, "prev_close": 0, "volume": 0, "change": 0, "change_pct": 0}


def resolve_exchange_token(groww, symbol: str) -> str:
    """Look up exchange_token for GrowwFeed subscription."""
    instrument = groww.get_instrument_by_exchange_and_trading_symbol("NSE", symbol)
    return str(instrument.get("exchange_token", ""))


def _to_unix(ts) -> int:
    """Convert various timestamp formats to Unix seconds."""
    if isinstance(ts, (int, float)):
        # Already numeric — if in milliseconds, convert to seconds
        return int(ts) if ts < 1e12 else int(ts / 1000)
    if isinstance(ts, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return int(datetime.strptime(ts, fmt).timestamp())
            except ValueError:
                continue
        try:
            return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except Exception:
            pass
    return int(time.time())
