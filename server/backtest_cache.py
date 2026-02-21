"""
Persistent SQLite cache for historical candle data used by the backtest engine.

Cache key: (groww_symbol, segment, interval, date). Data is stored at day granularity.
Fetches from Groww API in chunks respecting max-duration-per-request limits.
"""

import json
import logging
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "backtest_cache.db")

# Max calendar days per API request by candle interval (Groww Backtesting API docs)
INTERVAL_MAX_DAYS = {
    "1minute": 30,
    "1 min": 30,
    "2minute": 30,
    "2 min": 30,
    "3minute": 30,
    "3 min": 30,
    "5minute": 30,
    "5 min": 30,
    "10minute": 90,
    "10 min": 90,
    "15minute": 90,
    "15 min": 90,
    "30minute": 90,
    "30 min": 90,
    "1hour": 180,
    "1 hour": 180,
    "4hours": 180,
    "4 hours": 180,
    "1day": 180,
    "1 day": 180,
    "1week": 180,
    "1 week": 180,
    "1month": 180,
    "1 month": 180,
}

# Groww API expects interval without spaces: "5minute", "1day", etc. (see curl_historical_candles.sh)
DEFAULT_MAX_DAYS = 30

# NSE/BSE market hours (IST) for request range — only request within trading session
MARKET_START_TIME = "09:15:00"
MARKET_END_TIME = "15:30:00"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candle_cache (
            groww_symbol TEXT NOT NULL,
            segment TEXT NOT NULL,
            interval TEXT NOT NULL,
            date TEXT NOT NULL,
            candles_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (groww_symbol, segment, interval, date)
        )
    """)
    conn.commit()


def _to_unix(ts: Any) -> int:
    """Convert various timestamp formats to Unix seconds."""
    import time
    if isinstance(ts, (int, float)):
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


def _normalize_candle(c: Any) -> Optional[dict]:
    """Normalize a single candle to {time, open, high, low, close, volume, open_interest}."""
    try:
        if isinstance(c, dict):
            ts = c.get("timestamp") or c.get("time") or c.get("date", "")
            return {
                "time": _to_unix(ts),
                "open": float(c.get("open") or 0),
                "high": float(c.get("high") or 0),
                "low": float(c.get("low") or 0),
                "close": float(c.get("close") or 0),
                "volume": int(c.get("volume") or 0),
                "open_interest": int(c.get("open_interest") or c.get("oi") or 0),
            }
        if isinstance(c, (list, tuple)) and len(c) >= 5:
            oi = int(c[6]) if len(c) > 6 and c[6] is not None else 0
            return {
                "time": _to_unix(c[0]),
                "open": float(c[1] or 0),
                "high": float(c[2] or 0),
                "low": float(c[3] or 0),
                "close": float(c[4] or 0),
                "volume": int(c[5] or 0) if len(c) > 5 else 0,
                "open_interest": oi,
            }
    except (TypeError, ValueError):
        pass
    return None


def _parse_candles_response(raw: Any) -> List[dict]:
    """Parse API response into list of normalized candle dicts."""
    data_list = raw if isinstance(raw, list) else raw.get("candles", raw.get("data", []))
    out = []
    for c in data_list:
        row = _normalize_candle(c)
        if row and row["open"] > 0 and row["close"] > 0:
            out.append(row)
    return out


def _interval_max_days(interval: str) -> int:
    """Return max calendar days per request for this interval."""
    return INTERVAL_MAX_DAYS.get(interval, DEFAULT_MAX_DAYS)


def get_candles(
    groww: Any,
    groww_symbol: str,
    segment: str,
    interval: str,
    start_date: str,
    end_date: str,
    exchange: str = "NSE",
) -> List[dict]:
    """
    Return historical candles for the given symbol/segment/interval and date range.
    Uses SQLite cache; fetches only missing chunks from Groww (respecting max-duration limits).
    """
    if isinstance(start_date, datetime):
        start_date = start_date.strftime("%Y-%m-%d")
    if isinstance(end_date, datetime):
        end_date = end_date.strftime("%Y-%m-%d")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    if start_dt > end_dt:
        return []

    conn = _get_conn()
    _init_schema(conn)
    max_days = _interval_max_days(interval)

    # Collect all calendar days in range
    all_dates = []
    d = start_dt
    while d <= end_dt:
        all_dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    # Load from cache
    cached_by_date = {}
    placeholders = ",".join("?" for _ in all_dates)
    cursor = conn.execute(
        "SELECT date, candles_json FROM candle_cache "
        "WHERE groww_symbol = ? AND segment = ? AND interval = ? AND date IN (%s)"
        % placeholders,
        [groww_symbol, segment, interval] + all_dates,
    )
    for row in cursor.fetchall():
        date_str, candles_json = row[0], row[1]
        try:
            cached_by_date[date_str] = json.loads(candles_json)
        except Exception:
            pass
    conn.close()

    # Identify missing date ranges (contiguous)
    missing_dates = [d for d in all_dates if d not in cached_by_date]

    if missing_dates:
        # Fetch missing in chunks of max_days
        missing_dt = [datetime.strptime(d, "%Y-%m-%d") for d in missing_dates]
        i = 0
        while i < len(missing_dt):
            chunk_start = missing_dt[i]
            max_chunk_end = min(
                chunk_start + timedelta(days=max_days - 1),
                missing_dt[-1],
            )
            chunk_end = chunk_start
            for j in range(i, len(missing_dt)):
                if missing_dt[j] <= max_chunk_end:
                    chunk_end = missing_dt[j]
                else:
                    break
            start_str = chunk_start.strftime("%Y-%m-%d " + MARKET_START_TIME)
            end_str = chunk_end.strftime("%Y-%m-%d " + MARKET_END_TIME)
            try:
                raw = groww.get_historical_candles(
                    exchange=exchange,
                    segment=segment,
                    groww_symbol=groww_symbol,
                    start_time=start_str,
                    end_time=end_str,
                    candle_interval=interval,
                )
                # Log response shape for debugging (avoid dumping full payloads)
                if isinstance(raw, dict):
                    logger.debug(
                        "Backtest cache: API response keys=%s, candles_len=%s",
                        list(raw.keys()),
                        len(raw.get("candles", raw.get("data", []))),
                    )
                else:
                    logger.debug("Backtest cache: API response type=%s len=%s", type(raw).__name__, len(raw) if isinstance(raw, (list, tuple)) else "?")
                candles = _parse_candles_response(raw)
                logger.info(
                    "Backtest cache: fetched %d candles for %s %s (%s to %s)",
                    len(candles), groww_symbol, interval, start_str, end_str,
                )
                if len(candles) == 0:
                    # Help debug empty data: log response shape/sample
                    raw_preview = raw
                    if isinstance(raw, dict) and len(str(raw)) > 500:
                        raw_preview = {k: (v[:2] if isinstance(v, list) and len(v) > 2 else v) for k, v in raw.items()}
                    logger.warning(
                        "Backtest cache: API returned 0 candles for %s %s (%s–%s). Response: %s",
                        groww_symbol, interval, start_str, end_str,
                        str(raw_preview)[:500],
                    )
            except Exception as e:
                logger.warning(
                    "Backtest cache: fetch failed %s %s %s-%s: %s",
                    groww_symbol, interval, start_str, end_str, e,
                )
                raise

            # Split by calendar day and store
            by_date = defaultdict(list)
            for c in candles:
                dt = datetime.utcfromtimestamp(c["time"])
                date_key = dt.strftime("%Y-%m-%d")
                by_date[date_key].append(c)

            conn = _get_conn()
            fetched_at = datetime.utcnow().isoformat()
            for date_key, day_candles in by_date.items():
                day_candles.sort(key=lambda x: x["time"])
                cached_by_date[date_key] = day_candles
                conn.execute(
                    "INSERT OR REPLACE INTO candle_cache "
                    "(groww_symbol, segment, interval, date, candles_json, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        groww_symbol,
                        segment,
                        interval,
                        date_key,
                        json.dumps(day_candles),
                        fetched_at,
                    ),
                )
            conn.commit()
            conn.close()

            # Advance i past the chunk we just filled
            while i < len(missing_dt) and missing_dt[i] <= chunk_end:
                i += 1

    # Merge and sort all candles for requested range
    result = []
    for d in all_dates:
        result.extend(cached_by_date.get(d, []))
    result.sort(key=lambda x: x["time"])
    # Dedupe by time (in case of overlap)
    seen = set()
    deduped = []
    for c in result:
        t = c["time"]
        if t not in seen:
            seen.add(t)
            deduped.append(c)
    return deduped


def get_cache_stats() -> dict:
    """Return cache statistics: total entries, size, oldest/newest data."""
    conn = _get_conn()
    _init_schema(conn)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM candle_cache"
        ).fetchone()[0]
        size_bytes = conn.execute(
            "SELECT SUM(LENGTH(candles_json)) FROM candle_cache"
        ).fetchone()[0] or 0
        oldest = conn.execute(
            "SELECT MIN(date) FROM candle_cache"
        ).fetchone()[0]
        newest = conn.execute(
            "SELECT MAX(date) FROM candle_cache"
        ).fetchone()[0]
        return {
            "total_entries": total,
            "size_bytes": size_bytes,
            "oldest_date": oldest,
            "newest_date": newest,
        }
    finally:
        conn.close()


def clear_cache(groww_symbol: Optional[str] = None) -> int:
    """Purge cache. If groww_symbol is set, clear only that symbol; else clear all. Returns count deleted."""
    conn = _get_conn()
    _init_schema(conn)
    try:
        if groww_symbol:
            cursor = conn.execute(
                "DELETE FROM candle_cache WHERE groww_symbol = ?",
                (groww_symbol,),
            )
        else:
            cursor = conn.execute("DELETE FROM candle_cache")
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()
