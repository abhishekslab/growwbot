"""
Walk-forward backtest engine for a single symbol.

Uses cached historical candles, runs algo.evaluate() at each candle,
manages simulated positions (SL/target), computes metrics and yields SSE events.
"""

import json
import math
import os
import time
from datetime import date, datetime
from typing import Any, Dict, Generator, List, Optional

# #region agent log
_DBG_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cursor", "debug.log")
def _dbg(msg, data, hyp="general"):
    try:
        os.makedirs(os.path.dirname(_DBG_LOG), exist_ok=True)
        with open(_DBG_LOG, "a") as _f:
            _f.write(json.dumps({"timestamp": int(time.time()*1000), "location": "backtest_engine.py", "hypothesisId": hyp, "message": msg, "data": data}) + "\n")
    except Exception:
        pass
# #endregion


from position_monitor import calculate_fees, compute_exit_pnl

from backtest_cache import get_candles as cache_get_candles


def _compute_metrics(
    initial_capital: float,
    trades: List[dict],
    equity_curve: List[dict],
) -> dict:
    """Compute backtest metrics from closed trades and equity curve."""
    if not trades:
        total_pnl = 0.0
        total_fees = 0.0
        wins = 0
        losses = 0
        gross_profit = 0.0
        gross_loss = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        best_trade = 0.0
        worst_trade = 0.0
        avg_duration_sec = 0.0
    else:
        total_pnl = sum(t["pnl"] for t in trades)
        total_fees = sum(t.get("fees", 0) for t in trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        losses = sum(1 for t in trades if t["pnl"] <= 0)
        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = sum(t["pnl"] for t in trades if t["pnl"] < 0)
        win_trades = [t["pnl"] for t in trades if t["pnl"] > 0]
        loss_trades = [t["pnl"] for t in trades if t["pnl"] < 0]
        avg_win = (sum(win_trades) / len(win_trades)) if win_trades else 0.0
        avg_loss = (sum(loss_trades) / len(loss_trades)) if loss_trades else 0.0
        best_trade = max(t["pnl"] for t in trades) if trades else 0.0
        worst_trade = min(t["pnl"] for t in trades) if trades else 0.0
        durations = []
        for t in trades:
            et = t.get("exit_time")
            st = t.get("entry_time")
            if et is not None and st is not None:
                durations.append(et - st)
        avg_duration_sec = sum(durations) / len(durations) if durations else 0.0

    final_equity = initial_capital + total_pnl if trades else initial_capital
    if equity_curve:
        final_equity = equity_curve[-1]["equity"]
    total_return_pct = (
        (final_equity - initial_capital) / initial_capital * 100.0
        if initial_capital > 0
        else 0.0
    )
    win_rate = (wins / len(trades) * 100.0) if trades else 0.0
    profit_factor = (
        (gross_profit / abs(gross_loss)) if gross_loss < 0 else (float("inf") if gross_profit > 0 else 0.0)
    )
    expectancy = (avg_win * (wins / len(trades)) + avg_loss * (losses / len(trades))) if trades else 0.0

    # Max drawdown from equity curve
    peak = initial_capital
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    for point in equity_curve:
        eq = point["equity"]
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_drawdown:
            max_drawdown = dd
        if peak > 0:
            dd_pct = dd / peak * 100.0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

    # Daily returns for Sharpe/Sortino (bucket equity curve by day)
    daily_equity = {}
    for point in equity_curve:
        dt = datetime.utcfromtimestamp(point["time"])
        day_key = dt.strftime("%Y-%m-%d")
        daily_equity[day_key] = point["equity"]
    sorted_days = sorted(daily_equity.keys())
    daily_returns = []
    for i in range(1, len(sorted_days)):
        prev_eq = daily_equity[sorted_days[i - 1]]
        curr_eq = daily_equity[sorted_days[i]]
        if prev_eq > 0:
            daily_returns.append((curr_eq - prev_eq) / prev_eq)
    if not daily_returns:
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
    else:
        mean_ret = sum(daily_returns) / len(daily_returns)
        std_ret = math.sqrt(
            sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
        )
        sharpe_ratio = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0
        downside_returns = [r for r in daily_returns if r < 0]
        downside_std = (
            math.sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns))
            if downside_returns
            else 0.0
        )
        sortino_ratio = (
            (mean_ret / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0
        )

    return {
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "total_fees": round(total_fees, 2),
        "net_pnl": round(total_pnl, 2),
        "trade_count": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "expectancy": round(expectancy, 2),
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "avg_duration_seconds": round(avg_duration_sec, 1),
    }


def run_backtest(
    groww: Any,
    algo: Any,
    groww_symbol: str,
    exchange: str,
    segment: str,
    start_date: str,
    end_date: str,
    candle_interval: str,
    initial_capital: float,
    risk_percent: float = 1.0,
    max_positions: int = 1,
) -> Generator[dict, None, None]:
    """
    Run a single-symbol backtest. Yields SSE-style events: progress, trade, complete.
    """
    # Validate date range
    today = date.today().isoformat()
    if start_date > end_date:
        yield {
            "event_type": "complete",
            "error": "Start date must be before or equal to end date.",
            "metrics": {},
            "trades": [],
            "equity_curve": [],
        }
        return
    if end_date > today:
        yield {
            "event_type": "complete",
            "error": "End date cannot be in the future. Use a date range up to today (%s)." % today,
            "metrics": {},
            "trades": [],
            "equity_curve": [],
        }
        return

    candles = cache_get_candles(
        groww, groww_symbol, segment, candle_interval, start_date, end_date, exchange
    )
    total_bars = len(candles)
    if total_bars == 0:
        yield {
            "event_type": "complete",
            "error": (
                "No candle data for the given range. Check that: (1) Groww symbol is correct "
                "(e.g. NSE-RELIANCE for CASH, not just RELIANCE), (2) the date range contains "
                "trading days, (3) the range is not before 2020 (API data from 2020)."
            ),
            "metrics": {},
            "trades": [],
            "equity_curve": [],
        }
        return

    algo.set_runtime_params(initial_capital, risk_percent)
    open_position = None  # type: Optional[dict]
    trades = []  # type: List[dict]
    equity_curve = []  # type: List[dict]
    realized_pnl = 0.0

    for i, candle in enumerate(candles):
        current_equity = initial_capital + realized_pnl
        if open_position:
            entry = open_position["entry_price"]
            sl = open_position["stop_loss"]
            target = open_position["target"]
            high = candle["high"]
            low = candle["low"]
            exit_price = None
            exit_trigger = None
            if high >= target and low <= sl:
                # Both hit: use relative distance from open to decide
                open_p = candle.get("open", entry)
                if abs(target - open_p) <= abs(open_p - sl):
                    exit_price = target
                    exit_trigger = "TARGET"
                else:
                    exit_price = sl
                    exit_trigger = "SL"
            elif high >= target:
                exit_price = target
                exit_trigger = "TARGET"
            elif low <= sl:
                exit_price = sl
                exit_trigger = "SL"

            if exit_price is not None and exit_trigger:
                qty = open_position["quantity"]
                trade_type = open_position.get("trade_type", "INTRADAY")
                net_pnl, total_fees = compute_exit_pnl(
                    entry, exit_price, qty, trade_type
                )
                realized_pnl += net_pnl
                closed = {
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "quantity": qty,
                    "entry_time": open_position["entry_time"],
                    "exit_time": candle["time"],
                    "pnl": net_pnl,
                    "fees": total_fees,
                    "exit_trigger": exit_trigger,
                    "reason": open_position.get("reason", ""),
                }
                trades.append(closed)
                current_equity = initial_capital + realized_pnl
                yield {"event_type": "trade", "trade": closed}
                open_position = None

        equity_curve.append({"time": candle["time"], "equity": current_equity})

        if open_position is None and i >= 30:
            algo.set_runtime_params(initial_capital + realized_pnl, risk_percent)
            candidate_info = {
                "symbol": groww_symbol,
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle.get("volume", 0),
                "open_interest": candle.get("open_interest", 0),
            }
            try:
                signal = algo.evaluate(
                    groww_symbol, candles[: i + 1], candle["close"], candidate_info
                )
            except Exception:
                signal = None
            if signal and signal.action == "BUY" and max_positions >= 1:
                open_position = {
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "target": signal.target,
                    "quantity": signal.quantity,
                    "entry_time": candle["time"],
                    "trade_type": "INTRADAY",
                    "reason": signal.reason or "",
                }

        if total_bars > 0 and (i % max(1, total_bars // 20) == 0 or i == total_bars - 1):
            pct = (i + 1) / total_bars * 100.0
            ts_str = datetime.utcfromtimestamp(candle["time"]).strftime("%Y-%m-%d %H:%M")
            yield {
                "event_type": "progress",
                "percent": round(pct, 1),
                "current_date": ts_str,
                "bars_processed": i + 1,
                "total_bars": total_bars,
            }

    # #region agent log
    _dbg("First candle sample", {"candle_0": candles[0] if candles else None, "candle_30": candles[30] if len(candles) > 30 else None, "runId": "post-fix"}, "data-check")
    rejection_counts = getattr(algo, "_dbg_counts", {})
    _dbg("Rejection summary (post-fix)", {"total_bars": total_bars, "trades": len(trades), "rejections": rejection_counts, "signal_analysis_keys": list(signal_analysis.keys()), "runId": "post-fix"}, "summary")
    # #endregion

    _REJECTION_LABELS = {
        "H-A_ema_bearish": "EMA Bearish (EMA9 ≤ EMA21) — no uptrend",
        "H-B_no_crossover": "No Recent Crossover (last 3 bars)",
        "H-C_rsi_oob": "RSI Out of Range (must be 40–65)",
        "H-D_vol_low": "Volume Below 1.5× Average",
        "H-E_below_vwap": "Price Below VWAP",
        "H-F_fee_margin": "Fee Margin Too High for ATR-based target",
    }
    raw_counts = getattr(algo, "_dbg_counts", {})
    signal_analysis = {_REJECTION_LABELS.get(k, k): v for k, v in raw_counts.items()} if raw_counts else {}

    metrics = _compute_metrics(initial_capital, trades, equity_curve)
    yield {
        "event_type": "complete",
        "metrics": metrics,
        "trades": trades,
        "equity_curve": equity_curve,
        "signal_analysis": signal_analysis,
    }
