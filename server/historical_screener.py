"""
Historical daily picks screener - computes daily picks from historical candles.

This module simulates what the live screener would have returned on a historical date,
using EOD candles instead of live market data.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from backtest_cache import get_daily_candles, get_daily_picks_snapshot, save_daily_picks_snapshot

logger = logging.getLogger(__name__)

# FnO symbols (approximate - ideally should be loaded from historical data)
# This is a static list for backtesting purposes
FNO_SYMBOLS = {
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "HINDUNILVR",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "KOTAKBANK",
    "LT",
    "AXISBANK",
    "ASIANPAINT",
    "MARUTI",
    "TITAN",
    "BAJFINANCE",
    "HCLTECH",
    "SUNPHARMA",
    "WIPRO",
    "ULTRACEMCO",
    "NESTLEIND",
    "TECHM",
    "POWERGRID",
    "NTPC",
    "BAJAJFINSV",
    "INDUSINDBK",
    "TATAMOTORS",
    "GRASIM",
    "JSWSTEEL",
    "M&M",
    "HDFC",
    "ADANIENT",
    "ADANIPORTS",
    "COALINDIA",
    "TATASTEEL",
    "ONGC",
    "CIPLA",
    "DIVISLAB",
    "DRREDDY",
    "EICHERMOT",
    "HEROMOTOCO",
    "HINDALCO",
    "APOLLOHOSP",
    "BRITANNIA",
    "BPCL",
    "DABUR",
    "GAIL",
    "HAL",
    "IOC",
    "M&M",
    "PIDILITIND",
    "SHREECEM",
    "SBILIFE",
    "TATACONSUM",
    "TATAPOWER",
    "UPL",
    "VEDL",
    "ZOMATO",
    "PAYTM",
    "POLYCAB",
    "DMART",
    "BAJAJ_AUTO",
    "GODREJCP",
    "HAVELLS",
    "ICICIPRULI",
    "INDIGO",
    "JINDALSTEL",
    "LUPIN",
    "MCDOWELL_N",
    "MOTHERSON",
    "NAUKRI",
    "PGHH",
    "SIEMENS",
    "SRF",
    "TORNTPHARM",
    "TVSMOTOR",
    "YESBANK",
    "IDEA",
    "VODAFONE",
    "BANDHANBNK",
    "BANKBARODA",
    "BEL",
    "BHEL",
    "CANBK",
    "CHOLAFIN",
    "CUMMINSIND",
    "DLF",
    "EXIDEIND",
    "FEDERALBNK",
    "GLENMARK",
    "GMRINFRA",
    "IDFCFIRSTB",
    "INDHOTEL",
    "INDIANB",
    "IRCTC",
    "JUBLFOOD",
    "LICHSGFIN",
    "LTIM",
    "MANAPPURAM",
    "MFSL",
    "MGL",
    "MUTHOOTFIN",
    "NATIONALUM",
    "NAVINFLUOR",
    "NMDC",
    "OBEROIRLTY",
    "PEL",
    "PFC",
    "PNB",
    "RBLBANK",
    "RECLTD",
    "SAIL",
    "SUNTV",
    "SYNGENE",
    "TATACHEM",
    "TATACOMM",
    "TATAELXSI",
    "TORNTPOWER",
    "TRENT",
    "VOLTAS",
    "WHIRLPOOL",
    "ZEEL",
    "ZYDUSLIFE",
}


def _load_instruments(groww: Any, cache: Any = None) -> List[dict]:
    """Load NSE CASH instruments. Returns list of dicts with symbol and name."""
    try:
        if cache:
            df = cache.get_instruments(groww)
        else:
            df = groww.get_all_instruments()

        # Filter to NSE CASH
        if "exchange" in df.columns and "segment" in df.columns:
            mask = (df["exchange"] == "NSE") & (df["segment"] == "CASH")
            df = df[mask]
        elif "exchange" in df.columns:
            df = df[df["exchange"] == "NSE"]

        # Keep only EQ series
        if "series" in df.columns:
            df = df[df["series"].isin(["EQ", "BE", "SM", "ST"])]

        # Build list of instruments
        instruments = []
        for _, row in df.iterrows():
            symbol = row.get("trading_symbol", "")
            name = row.get("name", symbol)
            if symbol:
                instruments.append({"symbol": symbol, "name": name if name else symbol})

        return instruments
    except Exception as e:
        logger.error("Failed to load instruments: %s", e)
        return []


def _fetch_daily_candle_batch(groww: Any, instruments: List[dict], date: str, cache: Any = None) -> List[dict]:
    """Fetch daily candles for a batch of instruments."""
    results = []

    def fetch_single(inst: dict) -> Optional[dict]:
        try:
            candle = get_daily_candles(groww, inst["symbol"], date)
            if candle:
                return {
                    "symbol": inst["symbol"],
                    "name": inst["name"],
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"],
                }
        except Exception as e:
            logger.debug("Failed to fetch daily candle for %s: %s", inst["symbol"], e)
        return None

    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_inst = {executor.submit(fetch_single, inst): inst for inst in instruments}
        for future in as_completed(future_to_inst):
            result = future.result()
            if result:
                results.append(result)

    return results


def run_daily_picks_historical(
    groww: Any,
    date: str,
    cache: Any = None,
    use_cached_snapshot: bool = True,
    price_range: tuple = (50, 50000),
    min_turnover: int = 5_000_000,
) -> Optional[dict]:
    """
    Simulate run_daily_picks() for a historical date.

    Args:
        groww: Groww client instance
        date: Date string (YYYY-MM-DD)
        cache: Cache instance (optional)
        use_cached_snapshot: If True, use cached snapshot if available
        price_range: (min_price, max_price) filter
        min_turnover: Minimum turnover in ₹ (default ₹50L)

    Returns:
        dict with same format as run_daily_picks(): {"candidates": [...], "meta": {...}}
    """
    # Check cache first
    if use_cached_snapshot:
        cached = get_daily_picks_snapshot(date)
        if cached:
            logger.info("Using cached daily picks snapshot for %s", date)
            return cached

    logger.info("Computing daily picks for %s", date)
    start_time = datetime.now()

    # Load instruments
    instruments = _load_instruments(groww, cache)
    total_instruments = len(instruments)

    if not instruments:
        logger.error("No instruments loaded")
        return None

    # Stage 1: Fetch daily candles for all instruments
    # Process in batches to avoid overwhelming the API
    batch_size = 50
    all_candles = []

    for i in range(0, len(instruments), batch_size):
        batch = instruments[i : i + batch_size]
        candles = _fetch_daily_candle_batch(groww, batch, date, cache)
        all_candles.extend(candles)
        logger.debug("Fetched batch %d/%d: %d candles", i // batch_size + 1, (len(instruments) + batch_size - 1) // batch_size, len(candles))

    candidates_after_price = len(all_candles)

    # Stage 2: Filter by price range and calculate day_change_pct
    min_price, max_price = price_range
    filtered = []

    for c in all_candles:
        close = c["close"]
        if not (min_price <= close <= max_price):
            continue

        open_price = c["open"]
        if open_price <= 0:
            continue

        day_change_pct = ((close - open_price) / open_price) * 100

        filtered.append(
            {
                "symbol": c["symbol"],
                "name": c["name"],
                "ltp": round(close, 2),
                "open": round(open_price, 2),
                "day_change_pct": round(day_change_pct, 2),
                "volume": c["volume"],
                "turnover": round(c["volume"] * close, 2),
            }
        )

    # Stage 3: Select top movers
    # Split into FnO and non-FnO
    fno_candidates = [c for c in filtered if c["symbol"] in FNO_SYMBOLS]
    fno_candidates.sort(key=lambda x: x["day_change_pct"], reverse=True)
    top_fno = fno_candidates[:30]

    non_fno = [c for c in filtered if c["symbol"] not in FNO_SYMBOLS]
    non_fno.sort(key=lambda x: x["day_change_pct"], reverse=True)
    top_non_fno = non_fno[:100]

    # Merge and deduplicate
    seen = set()
    candidates = []
    for c in top_non_fno + top_fno:
        if c["symbol"] not in seen:
            seen.add(c["symbol"])
            candidates.append(c)

    candidates_volume_enriched = len(candidates)

    # Stage 4: Tag with criteria flags
    passes_gainer = 0
    passes_volume_leader = 0
    passes_hc = 0

    for c in candidates:
        meets_turnover = c["turnover"] >= min_turnover
        c["fno_eligible"] = c["symbol"] in FNO_SYMBOLS
        c["meets_gainer_criteria"] = meets_turnover and c["volume"] >= 100_000
        c["meets_volume_leader_criteria"] = meets_turnover and c["volume"] >= 500_000
        c["high_conviction"] = meets_turnover and c["volume"] >= 100_000 and c["fno_eligible"]

        # Add empty news fields (skipped in backtest)
        c["news_headline"] = ""
        c["news_link"] = ""

        if c["meets_gainer_criteria"]:
            passes_gainer += 1
        if c["meets_volume_leader_criteria"]:
            passes_volume_leader += 1
        if c["high_conviction"]:
            passes_hc += 1

    scan_time = (datetime.now() - start_time).total_seconds()

    result = {
        "candidates": candidates,
        "meta": {
            "total_instruments_scanned": total_instruments,
            "candidates_after_price_filter": candidates_after_price,
            "candidates_volume_enriched": candidates_volume_enriched,
            "passes_gainer_criteria": passes_gainer,
            "passes_volume_leader_criteria": passes_volume_leader,
            "high_conviction_count": passes_hc,
            "fno_eligible_universe": len(FNO_SYMBOLS),
            "scan_time_seconds": round(scan_time, 2),
            "cache_active": True,
            "scan_timestamp": datetime.now().isoformat(),
            "historical": True,
            "date": date,
        },
    }

    # Cache the result
    save_daily_picks_snapshot(date, result)
    logger.info("Daily picks for %s: %d candidates (%.2fs)", date, len(candidates), scan_time)

    return result


def clear_historical_snapshots() -> int:
    """Clear all cached daily picks snapshots. Returns count deleted."""
    from backtest_cache import _get_conn, _init_schema

    conn = _get_conn()
    _init_schema(conn)
    try:
        cursor = conn.execute("DELETE FROM daily_picks_snapshots")
        deleted = cursor.rowcount
        conn.commit()
        logger.info("Cleared %d daily picks snapshots", deleted)
        return deleted
    finally:
        conn.close()


if __name__ == "__main__":
    # Test the historical screener
    import sys

    sys.path.insert(0, os.path.dirname(__file__))

    from infrastructure.groww_client import get_groww_client

    logging.basicConfig(level=logging.INFO)

    # Test with a single date
    test_date = "2025-02-10"
    groww = get_groww_client()

    result = run_daily_picks_historical(groww, test_date)

    if result:
        print(f"\nDaily picks for {test_date}:")
        print(f"Total candidates: {len(result['candidates'])}")
        print(f"High conviction: {result['meta']['high_conviction_count']}")
        print("\nTop 10 candidates:")
        for c in result["candidates"][:10]:
            print(f"  {c['symbol']}: {c['day_change_pct']:+.2f}% (₹{c['ltp']:.2f})")
    else:
        print("Failed to compute daily picks")
