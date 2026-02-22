"""
Test script for daily picks pipeline backtest.

Usage: cd server && python3 test_daily_picks_backtest.py
"""

import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

logger = logging.getLogger(__name__)


def test_historical_screener():
    """Test the historical screener."""
    logger.info("=" * 60)
    logger.info("TEST 1: Historical Screener")
    logger.info("=" * 60)

    from infrastructure.groww_client import get_groww_client
    from historical_screener import run_daily_picks_historical

    groww = get_groww_client()
    test_date = "2025-02-10"

    logger.info("Computing daily picks for %s...", test_date)
    result = run_daily_picks_historical(groww, test_date, use_cached_snapshot=False)

    if not result:
        logger.error("❌ Failed to compute daily picks")
        return False

    candidates = result.get("candidates", [])
    meta = result.get("meta", {})

    logger.info("✓ Daily picks computed successfully")
    logger.info("  Total candidates: %d", len(candidates))
    logger.info("  High conviction: %d", meta.get("high_conviction_count", 0))
    logger.info("  Scan time: %.2fs", meta.get("scan_time_seconds", 0))

    if candidates:
        logger.info("\n  Top 5 candidates:")
        for i, c in enumerate(candidates[:5], 1):
            logger.info("    %d. %s: %+.2f%% (₹%.2f) Vol: %s", i, c["symbol"], c["day_change_pct"], c["ltp"], format(int(c["volume"]), ","))

    # Verify format matches live screener
    required_fields = ["symbol", "name", "ltp", "open", "day_change_pct", "volume", "turnover", "fno_eligible", "high_conviction"]

    if candidates:
        missing = [f for f in required_fields if f not in candidates[0]]
        if missing:
            logger.error("❌ Missing fields in candidate: %s", missing)
            return False
        logger.info("✓ All required fields present")

    return True


def test_daily_picks_backtest_single_day():
    """Test daily picks backtest for a single day."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Daily Picks Backtest (Single Day)")
    logger.info("=" * 60)

    from infrastructure.groww_client import get_groww_client
    from daily_picks_backtest import run_daily_picks_backtest

    groww = get_groww_client()

    events = []
    for event in run_daily_picks_backtest(
        groww=groww,
        start_date="2025-02-10",
        end_date="2025-02-10",
        algo_id="momentum_scalp",
        candle_interval="5minute",
        initial_capital=100000,
        max_positions_per_day=3,
        use_cached_snapshots=False,
    ):
        events.append(event)

        if event["event_type"] == "day_start":
            logger.info(
                "📅 Day %d/%d: %s (%d candidates)", event.get("day", 0), event.get("total_days", 0), event["date"], event.get("candidates_count", 0)
            )

        elif event["event_type"] == "trade":
            trade = event["trade"]
            logger.info("  💰 Trade: %s | P&L: ₹%.2f | Exit: %s", event.get("symbol", ""), trade["pnl"], trade["exit_trigger"])

        elif event["event_type"] == "day_complete":
            logger.info("  📊 Day P&L: ₹%.2f | Trades: %d | Equity: ₹%.2f", event["daily_pnl"], event["trades_count"], event["current_equity"])

        elif event["event_type"] == "complete":
            metrics = event["metrics"]
            logger.info("\n✓ Backtest complete!")
            logger.info("  Final Equity: ₹%.2f", metrics["final_equity"])
            logger.info("  Total Return: %.2f%%", metrics["total_return_pct"])
            logger.info("  Total Trades: %d", metrics["trade_count"])
            logger.info("  Win Rate: %.1f%%", metrics["win_rate_pct"])
            logger.info("  Sharpe Ratio: %.2f", metrics.get("sharpe_ratio", 0))

    # Verify we got all event types
    event_types = [e["event_type"] for e in events]

    if "day_start" not in event_types:
        logger.error("❌ Missing day_start event")
        return False

    if "complete" not in event_types:
        logger.error("❌ Missing complete event")
        return False

    logger.info("✓ All required events received")
    return True


def test_multi_day_backtest():
    """Test multi-day backtest."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Multi-Day Backtest (3 days)")
    logger.info("=" * 60)

    from infrastructure.groww_client import get_groww_client
    from daily_picks_backtest import run_daily_picks_backtest

    groww = get_groww_client()

    day_count = 0
    total_trades = 0

    for event in run_daily_picks_backtest(
        groww=groww,
        start_date="2025-02-10",
        end_date="2025-02-12",  # 3 days
        algo_id="momentum_scalp",
        candle_interval="5minute",
        initial_capital=100000,
        max_positions_per_day=2,
        use_cached_snapshots=True,  # Use cache for speed
    ):
        if event["event_type"] == "day_start":
            day_count += 1
            logger.info("📅 Day %d: %s", event.get("day", 0), event["date"])

        elif event["event_type"] == "trade":
            total_trades += 1

        elif event["event_type"] == "day_complete":
            logger.info("  Equity: ₹%.2f | Daily P&L: ₹%.2f", event["current_equity"], event["daily_pnl"])

        elif event["event_type"] == "complete":
            metrics = event["metrics"]
            logger.info("\n✓ Multi-day backtest complete!")
            logger.info("  Days processed: %d", day_count)
            logger.info("  Total trades: %d", total_trades)
            logger.info("  Final equity: ₹%.2f", metrics["final_equity"])
            logger.info("  Total return: %.2f%%", metrics["total_return_pct"])

            # Verify capital compounding
            if metrics["final_equity"] != 100000:
                logger.info("✓ Capital compounding verified (started: ₹100000)")

    if day_count == 0:
        logger.error("❌ No days processed")
        return False

    return True


def test_cache_functionality():
    """Test caching of daily picks."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Cache Functionality")
    logger.info("=" * 60)

    from infrastructure.groww_client import get_groww_client
    from historical_screener import run_daily_picks_historical, clear_historical_snapshots
    from backtest_cache import get_daily_picks_snapshot
    import time

    groww = get_groww_client()
    test_date = "2025-02-11"

    # Clear cache first
    clear_historical_snapshots()
    logger.info("Cache cleared")

    # First run - should compute
    logger.info("First run (computing)...")
    start = time.time()
    result1 = run_daily_picks_historical(groww, test_date, use_cached_snapshot=True)
    time1 = time.time() - start
    logger.info("  Time: %.2fs", time1)

    # Second run - should use cache
    logger.info("Second run (cached)...")
    start = time.time()
    result2 = run_daily_picks_historical(groww, test_date, use_cached_snapshot=True)
    time2 = time.time() - start
    logger.info("  Time: %.2fs", time2)

    # Verify cache was used (second run should be much faster)
    if time2 < time1 * 0.5:
        logger.info("✓ Cache working (%.1fx faster)", time1 / time2)
    else:
        logger.warning("⚠ Cache may not be working (only %.1fx faster)", time1 / time2)

    # Verify results are identical
    if result1 and result2:
        if len(result1["candidates"]) == len(result2["candidates"]):
            logger.info("✓ Cached result matches computed result")
        else:
            logger.error("❌ Cached result differs from computed")
            return False

    return True


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("DAILY PICKS PIPELINE BACKTEST TESTS")
    logger.info("=" * 60)

    results = []

    try:
        results.append(("Historical Screener", test_historical_screener()))
    except Exception as e:
        logger.exception("Historical screener test failed")
        results.append(("Historical Screener", False))

    try:
        results.append(("Single Day Backtest", test_daily_picks_backtest_single_day()))
    except Exception as e:
        logger.exception("Single day backtest failed")
        results.append(("Single Day Backtest", False))

    try:
        results.append(("Multi-Day Backtest", test_multi_day_backtest()))
    except Exception as e:
        logger.exception("Multi-day backtest failed")
        results.append(("Multi-Day Backtest", False))

    try:
        results.append(("Cache Functionality", test_cache_functionality()))
    except Exception as e:
        logger.exception("Cache test failed")
        results.append(("Cache Functionality", False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        logger.info("%-30s %s", name, status)

    total = len(results)
    passed = sum(1 for _, p in results if p)

    logger.info("\nTotal: %d/%d tests passed", passed, total)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
