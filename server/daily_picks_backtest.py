"""
Daily picks pipeline backtest engine.

Backtests the full trading pipeline across multiple days:
1. Compute/select daily picks for each day
2. Run intraday simulation on each candidate
3. Manage positions with EOD clearing (intraday mode)
4. Compound capital day-to-day
5. Generate portfolio-level metrics
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List, Optional

from backtest_cache import get_candles
from backtest_engine import _compute_metrics
from historical_screener import run_daily_picks_historical
from strategies.registry import StrategyRegistry
from utils.fees import compute_exit_pnl

logger = logging.getLogger(__name__)


def _is_trading_day(date: datetime) -> bool:
    """Check if date is a trading day (Mon-Fri, not holiday)."""
    # Weekday check (0=Monday, 6=Sunday)
    if date.weekday() >= 5:  # Saturday or Sunday
        return False
    # TODO: Add holiday calendar check
    return True


def _get_trading_days(start_date: str, end_date: str) -> List[str]:
    """Get list of trading days between start and end dates."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    trading_days = []
    current = start
    while current <= end:
        if _is_trading_day(current):
            trading_days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return trading_days


def _simulate_symbol_intraday(
    groww: Any,
    candidate: dict,
    date: str,
    algo: Any,
    candle_interval: str,
    current_equity: float,
    risk_percent: float,
    max_trade_duration_minutes: int = 15,
) -> List[dict]:
    """
    Simulate intraday trading for a single symbol.

    Returns list of completed trades.
    """
    symbol = candidate["symbol"]
    trades = []

    try:
        # Fetch intraday candles
        candles = get_candles(
            groww=groww, groww_symbol=symbol, segment="CASH", interval=candle_interval, start_date=date, end_date=date, exchange="NSE"
        )

        if not candles or len(candles) < 30:
            logger.debug("Insufficient candles for %s on %s", symbol, date)
            return trades

        # Walk-forward simulation
        open_position = None
        algo.set_runtime_params(current_equity, risk_percent)

        for i, candle in enumerate(candles):
            # Check existing position for exit
            if open_position:
                high = candle["high"]
                low = candle["low"]
                entry = open_position["entry_price"]
                target = open_position["target"]
                sl = open_position["stop_loss"]
                is_long = entry > sl

                triggered = None
                exit_price = None

                if is_long:
                    if low <= sl:
                        triggered = "SL"
                        exit_price = sl
                    elif high >= target:
                        triggered = "TARGET"
                        exit_price = target
                else:
                    if high >= sl:
                        triggered = "SL"
                        exit_price = sl
                    elif low <= target:
                        triggered = "TARGET"
                        exit_price = target

                # Check time-based exit
                if triggered is None:
                    entry_time = datetime.fromtimestamp(open_position["entry_time"])
                    current_time = datetime.fromtimestamp(candle["time"])
                    elapsed_minutes = (current_time - entry_time).total_seconds() / 60
                    if elapsed_minutes >= max_trade_duration_minutes:
                        triggered = "TIME_EXIT"
                        exit_price = candle["close"]

                if triggered:
                    # Close position
                    qty = open_position["quantity"]
                    trade_type = open_position["trade_type"]

                    net_pnl, total_fees = compute_exit_pnl(open_position["entry_price"], exit_price, qty, trade_type)

                    trade = {
                        "symbol": symbol,
                        "entry_price": open_position["entry_price"],
                        "exit_price": exit_price,
                        "quantity": qty,
                        "entry_time": open_position["entry_time"],
                        "exit_time": candle["time"],
                        "pnl": round(net_pnl, 2),
                        "fees": round(total_fees, 2),
                        "exit_trigger": triggered,
                        "reason": open_position.get("reason", ""),
                        "date": date,
                    }
                    trades.append(trade)
                    open_position = None

            # Evaluate for entry (if no open position and enough candles)
            if open_position is None and i >= 30:
                candidate_info = {
                    "symbol": symbol,
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle.get("volume", 0),
                    "open_interest": candle.get("open_interest", 0),
                    **candidate,  # Include all daily picks metadata
                }

                try:
                    signal = algo.evaluate(symbol, candles[: i + 1], candle["close"], candidate_info)
                    if signal and signal.action == "BUY":
                        open_position = {
                            "entry_price": signal.entry_price,
                            "stop_loss": signal.stop_loss,
                            "target": signal.target,
                            "quantity": signal.quantity,
                            "entry_time": candle["time"],
                            "trade_type": "INTRADAY",
                            "reason": signal.reason,
                        }
                except Exception as e:
                    logger.debug("Strategy evaluation error for %s: %s", symbol, e)

        # Close any open position at EOD
        if open_position:
            last_candle = candles[-1]
            exit_price = last_candle["close"]
            qty = open_position["quantity"]

            net_pnl, total_fees = compute_exit_pnl(open_position["entry_price"], exit_price, qty, "INTRADAY")

            trade = {
                "symbol": symbol,
                "entry_price": open_position["entry_price"],
                "exit_price": exit_price,
                "quantity": qty,
                "entry_time": open_position["entry_time"],
                "exit_time": last_candle["time"],
                "pnl": round(net_pnl, 2),
                "fees": round(total_fees, 2),
                "exit_trigger": "EOD",
                "reason": open_position.get("reason", ""),
                "date": date,
            }
            trades.append(trade)

    except Exception as e:
        logger.warning("Error simulating %s on %s: %s", symbol, date, e)

    return trades


def run_daily_picks_backtest(
    groww: Any,
    start_date: str,
    end_date: str,
    algo_id: str,
    candle_interval: str = "5minute",
    initial_capital: float = 100000,
    max_positions_per_day: int = 3,
    risk_percent: float = 1.0,
    max_trade_duration_minutes: int = 15,
    use_cached_snapshots: bool = True,
) -> Generator[dict, None, None]:
    """
    Run multi-day full pipeline backtest.

    Args:
        groww: Groww client instance
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        algo_id: Algorithm ID (e.g., "momentum_scalp")
        candle_interval: Candle interval ("1minute", "5minute", etc.)
        initial_capital: Starting capital
        max_positions_per_day: Max concurrent positions per day
        risk_percent: Risk per trade (%)
        max_trade_duration_minutes: Max trade duration before time exit
        use_cached_snapshots: Use cached daily picks if available

    Yields:
        SSE event dicts:
        - {"event_type": "day_start", "date": ..., "candidates": ...}
        - {"event_type": "trade", "date": ..., "trade": {...}}
        - {"event_type": "day_complete", "date": ..., "daily_pnl": ..., "trades_count": ...}
        - {"event_type": "complete", "metrics": {...}, "trades": [...], "equity_curve": [...]}
    """
    # Initialize strategy
    StrategyRegistry.initialize()
    algo = StrategyRegistry.get(algo_id, {})
    if not algo:
        yield {"event_type": "error", "error": f"Strategy not found: {algo_id}"}
        return

    # Get trading days
    trading_days = _get_trading_days(start_date, end_date)
    if not trading_days:
        yield {"event_type": "error", "error": "No trading days in range"}
        return

    logger.info("Starting daily picks backtest: %s to %s (%d days)", start_date, end_date, len(trading_days))

    # Track state across days
    current_equity = initial_capital
    all_trades = []
    equity_curve = [{"date": trading_days[0], "equity": initial_capital}]

    for day_idx, date in enumerate(trading_days):
        logger.info("Processing day %d/%d: %s", day_idx + 1, len(trading_days), date)

        # Step 1: Get daily picks for this date
        snapshot = run_daily_picks_historical(groww=groww, date=date, use_cached_snapshot=use_cached_snapshots)

        if not snapshot or not snapshot.get("candidates"):
            logger.warning("No daily picks for %s", date)
            yield {"event_type": "day_start", "date": date, "candidates_count": 0, "day": day_idx + 1, "total_days": len(trading_days)}
            continue

        candidates = snapshot["candidates"]

        yield {
            "event_type": "day_start",
            "date": date,
            "candidates_count": len(candidates),
            "high_conviction_count": snapshot["meta"].get("high_conviction_count", 0),
            "day": day_idx + 1,
            "total_days": len(trading_days),
            "current_equity": round(current_equity, 2),
        }

        # Step 2: Simulate intraday for each candidate
        daily_trades = []

        # Process candidates (limit to max_positions_per_day for performance)
        # Prioritize high conviction candidates
        hc_candidates = [c for c in candidates if c.get("high_conviction")]
        other_candidates = [c for c in candidates if not c.get("high_conviction")]

        # Sort by day_change_pct
        hc_candidates.sort(key=lambda x: x.get("day_change_pct", 0), reverse=True)
        other_candidates.sort(key=lambda x: x.get("day_change_pct", 0), reverse=True)

        # Take top candidates up to max_positions_per_day * 3 (to have enough opportunities)
        max_candidates = max_positions_per_day * 3
        selected_candidates = (hc_candidates + other_candidates)[:max_candidates]

        # Process in parallel
        def process_candidate(candidate: dict) -> List[dict]:
            return _simulate_symbol_intraday(
                groww=groww,
                candidate=candidate,
                date=date,
                algo=algo,
                candle_interval=candle_interval,
                current_equity=current_equity,
                risk_percent=risk_percent,
                max_trade_duration_minutes=max_trade_duration_minutes,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_candidate = {executor.submit(process_candidate, c): c for c in selected_candidates}

            for future in as_completed(future_to_candidate):
                candidate = future_to_candidate[future]
                try:
                    trades = future.result()
                    for trade in trades:
                        daily_trades.append(trade)
                        all_trades.append(trade)
                        yield {"event_type": "trade", "date": date, "trade": trade, "symbol": candidate["symbol"]}
                except Exception as e:
                    logger.warning("Error processing %s: %s", candidate["symbol"], e)

        # Step 3: Calculate daily P&L
        daily_pnl = sum(t["pnl"] for t in daily_trades)
        daily_fees = sum(t["fees"] for t in daily_trades)
        current_equity += daily_pnl

        equity_curve.append({"date": date, "equity": round(current_equity, 2), "daily_pnl": round(daily_pnl, 2), "daily_fees": round(daily_fees, 2)})

        yield {
            "event_type": "day_complete",
            "date": date,
            "daily_pnl": round(daily_pnl, 2),
            "daily_fees": round(daily_fees, 2),
            "trades_count": len(daily_trades),
            "current_equity": round(current_equity, 2),
            "day": day_idx + 1,
            "total_days": len(trading_days),
        }

    # Step 4: Compute final metrics
    metrics = _compute_metrics(initial_capital, all_trades, equity_curve)
    metrics["start_date"] = start_date
    metrics["end_date"] = end_date
    metrics["total_days"] = len(trading_days)
    metrics["trading_days"] = trading_days

    yield {
        "event_type": "complete",
        "metrics": metrics,
        "trades": all_trades,
        "equity_curve": equity_curve,
        "algo_id": algo_id,
        "candle_interval": candle_interval,
    }


if __name__ == "__main__":
    # Test the daily picks backtest
    import sys

    sys.path.insert(0, os.path.dirname(__file__))

    from infrastructure.groww_client import get_groww_client

    logging.basicConfig(level=logging.INFO)

    # Test with a single day
    groww = get_groww_client()

    for event in run_daily_picks_backtest(
        groww=groww,
        start_date="2025-02-10",
        end_date="2025-02-10",
        algo_id="momentum_scalp",
        candle_interval="5minute",
        initial_capital=100000,
        max_positions_per_day=3,
    ):
        print(f"\nEvent: {event['event_type']}")
        if event["event_type"] == "complete":
            print(f"Final equity: ₹{event['metrics']['final_equity']:,.2f}")
            print(f"Total return: {event['metrics']['total_return_pct']:.2f}%")
            print(f"Total trades: {event['metrics']['trade_count']}")
