"""
Algo trading engine — daemon thread that evaluates registered algorithms
on a 60-second cycle using Daily Picks as the symbol universe.

Creates paper trades via trades_db (same in-process pattern as PositionMonitor).
"""

import json
import os
import time
import logging
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from algo_base import BaseAlgorithm, AlgoSignal
from position_monitor import calculate_fees, compute_exit_pnl
from snapshot import load_snapshot
from trades_db import (
    create_trade, list_trades, update_trade, save_algo_signal,
    get_algo_settings, upsert_algo_settings, get_algo_net_pnl,
)

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "algo_config.json")

# IST offset: UTC+5:30
_IST_OFFSET = timedelta(hours=5, minutes=30)


def _load_config():
    # type: () -> dict
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load algo_config.json: %s, using defaults", e)
        return {
            "capital": 100000,
            "risk_percent": 1,
            "max_positions_per_algo": 3,
            "max_total_positions": 6,
            "trading_start_ist": "09:30",
            "trading_end_ist": "15:00",
            "force_close_ist": "15:15",
        }


def _ist_now():
    # type: () -> datetime
    """Current time in IST (UTC+5:30)."""
    return datetime.now(timezone.utc) + _IST_OFFSET


def _parse_ist_time(time_str):
    # type: (str) -> tuple
    """Parse 'HH:MM' string. Returns (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


class AlgoEngine:
    """Main orchestrator daemon for algo trading."""

    def __init__(self):
        self._running = False
        self._thread = None  # type: Optional[threading.Thread]
        self._algos = {}  # type: Dict[str, BaseAlgorithm]
        self._algo_enabled = {}  # type: Dict[str, bool]
        self._config = _load_config()
        self._cycle_interval = 60  # seconds
        self._signal_buffer = deque(maxlen=200)  # in-memory ring buffer
        self._last_cycle_time = 0.0
        self._cycle_count = 0

    def register_algo(self, algo):
        # type: (BaseAlgorithm) -> None
        """Register an algorithm. Loads persisted enabled state from DB."""
        self._algos[algo.ALGO_ID] = algo
        settings = get_algo_settings(algo.ALGO_ID)
        if settings:
            self._algo_enabled[algo.ALGO_ID] = bool(settings["enabled"])
        else:
            self._algo_enabled[algo.ALGO_ID] = True
            upsert_algo_settings(algo.ALGO_ID, {
                "enabled": 1,
                "capital": self._config.get("capital", 100000),
                "risk_percent": self._config.get("risk_percent", 1),
                "compounding": 0,
            })
        logger.info(
            "Registered algo: %s (%s) enabled=%s",
            algo.ALGO_ID, algo.ALGO_NAME, self._algo_enabled[algo.ALGO_ID],
        )

    def start(self):
        if self._running:
            return
        self._config = _load_config()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(
            "AlgoEngine started with %d algorithms: %s",
            len(self._algos), ", ".join(self._algos.keys()),
        )

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=15)
        logger.info("AlgoEngine stopped")

    def start_algo(self, algo_id):
        # type: (str) -> bool
        if algo_id in self._algos:
            self._algo_enabled[algo_id] = True
            upsert_algo_settings(algo_id, {"enabled": 1})
            logger.info("Algo %s enabled", algo_id)
            return True
        return False

    def stop_algo(self, algo_id):
        # type: (str) -> bool
        if algo_id in self._algos:
            self._algo_enabled[algo_id] = False
            upsert_algo_settings(algo_id, {"enabled": 0})
            logger.info("Algo %s disabled", algo_id)
            return True
        return False

    def get_effective_capital(self, algo_id):
        # type: (str) -> float
        """Compute effective capital for an algo, applying compounding if enabled."""
        settings = get_algo_settings(algo_id)
        if not settings:
            return self._config.get("capital", 100000)
        base_capital = settings.get("capital", 100000)
        if not settings.get("compounding"):
            return base_capital
        net_pnl = get_algo_net_pnl(algo_id, is_paper=True)
        # Cap at base so drawdowns don't reduce below starting capital
        return max(base_capital, base_capital + net_pnl)

    def update_algo_settings(self, algo_id, data):
        # type: (str, dict) -> Optional[dict]
        """Update settings for an algo. Syncs in-memory enabled state."""
        if algo_id not in self._algos:
            return None
        if "enabled" in data:
            self._algo_enabled[algo_id] = bool(data["enabled"])
            data["enabled"] = 1 if data["enabled"] else 0
        result = upsert_algo_settings(algo_id, data)
        return result

    def get_status(self):
        # type: () -> Dict[str, Any]
        """Return engine + per-algo status."""
        algos = []
        for algo_id, algo in self._algos.items():
            settings = get_algo_settings(algo_id) or {}
            base_capital = settings.get("capital", self._config.get("capital", 100000))
            compounding = bool(settings.get("compounding", 0))
            effective_capital = self.get_effective_capital(algo_id)
            compounding_pnl = get_algo_net_pnl(algo_id, is_paper=True) if compounding else 0
            algos.append({
                "algo_id": algo.ALGO_ID,
                "name": algo.ALGO_NAME,
                "description": algo.DESCRIPTION,
                "enabled": self._algo_enabled.get(algo_id, False),
                "capital": base_capital,
                "risk_percent": settings.get("risk_percent", self._config.get("risk_percent", 1)),
                "compounding": compounding,
                "effective_capital": effective_capital,
                "compounding_pnl": compounding_pnl,
            })
        return {
            "running": self._running,
            "cycle_interval": self._cycle_interval,
            "cycle_count": self._cycle_count,
            "last_cycle_time": self._last_cycle_time,
            "algos": algos,
        }

    def get_signals(self, algo_id=None, limit=50):
        # type: (Optional[str], int) -> List[dict]
        """Return recent signals from in-memory buffer."""
        signals = list(self._signal_buffer)
        if algo_id:
            signals = [s for s in signals if s.get("algo_id") == algo_id]
        return signals[:limit]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self):
        while self._running:
            try:
                now_ist = _ist_now()
                h, m = now_ist.hour, now_ist.minute
                current_minutes = h * 60 + m

                # Market hours: 9:20 - 15:30 IST
                if current_minutes < 9 * 60 + 20 or current_minutes > 15 * 60 + 30:
                    time.sleep(self._cycle_interval)
                    continue

                # Force-close at 15:15 IST
                fc_h, fc_m = _parse_ist_time(
                    self._config.get("force_close_ist", "15:15")
                )
                if current_minutes >= fc_h * 60 + fc_m:
                    self._force_close_all()
                    time.sleep(self._cycle_interval)
                    continue

                # Trading window check
                start_h, start_m = _parse_ist_time(
                    self._config.get("trading_start_ist", "09:30")
                )
                end_h, end_m = _parse_ist_time(
                    self._config.get("trading_end_ist", "15:00")
                )
                in_trading_window = (
                    start_h * 60 + start_m <= current_minutes <= end_h * 60 + end_m
                )

                if not in_trading_window:
                    time.sleep(self._cycle_interval)
                    continue

                self._run_cycle()

            except Exception:
                logger.exception("AlgoEngine loop error")

            time.sleep(self._cycle_interval)

    def _run_cycle(self):
        """Execute one evaluation cycle across all enabled algos."""
        self._cycle_count += 1
        cycle_start = time.time()

        # Load universe from Daily Picks snapshot
        snapshot = load_snapshot()
        if not snapshot or not snapshot.get("candidates"):
            return

        candidates = snapshot["candidates"]
        # Pre-filter: high conviction / gainer only
        filtered = [
            c for c in candidates
            if c.get("high_conviction") or c.get("meets_gainer_criteria")
        ]
        if not filtered:
            filtered = candidates[:20]  # fallback: top 20

        # Batch fetch LTP
        symbols = [c["symbol"] for c in filtered]
        ltp_map = self._fetch_ltp_batch(symbols)

        # Get current open positions for all algos
        open_positions = list_trades(status="OPEN", is_paper=True)
        total_open = len([p for p in open_positions if p.get("algo_id")])

        max_total = self._config.get("max_total_positions", 6)
        max_per_algo = self._config.get("max_positions_per_algo", 3)

        for algo_id, algo in self._algos.items():
            if not self._algo_enabled.get(algo_id, False):
                continue

            # Inject per-algo capital and risk settings
            effective_capital = self.get_effective_capital(algo_id)
            algo_settings = get_algo_settings(algo_id) or {}
            algo.set_runtime_params(
                effective_capital,
                algo_settings.get("risk_percent", self._config.get("risk_percent", 1)),
            )

            # Count positions for this algo
            algo_positions = [p for p in open_positions if p.get("algo_id") == algo_id]
            if len(algo_positions) >= max_per_algo:
                continue
            if total_open >= max_total:
                break

            for candidate in filtered:
                if total_open >= max_total:
                    break

                symbol = candidate["symbol"]
                ltp = ltp_map.get(symbol)
                if not ltp or ltp <= 0:
                    continue

                # Skip if algo already has position in this symbol
                if algo.should_skip_symbol(symbol, candidate, open_positions):
                    continue

                try:
                    # Fetch 1m candles
                    candles = self._fetch_candles(symbol)
                    if not candles or len(candles) < 30:
                        self._log_signal(algo_id, symbol, "SKIP", "Insufficient candle data")
                        continue

                    signal = algo.evaluate(symbol, candles, ltp, candidate)

                    if signal and signal.action == "BUY":
                        trade = self._execute_signal(signal)
                        if trade:
                            total_open += 1
                            open_positions.append(trade)
                            self._log_signal(
                                algo_id, symbol, "ENTRY",
                                signal.reason, trade_id=trade["id"],
                            )
                        else:
                            self._log_signal(algo_id, symbol, "SKIP", "Trade creation failed")
                    else:
                        self._log_signal(algo_id, symbol, "SKIP", "No signal")

                except Exception as e:
                    logger.warning("AlgoEngine: error evaluating %s/%s: %s", algo_id, symbol, e)
                    self._log_signal(algo_id, symbol, "ERROR", str(e))

        self._last_cycle_time = time.time() - cycle_start
        logger.debug(
            "AlgoEngine cycle #%d completed in %.1fs, %d candidates evaluated",
            self._cycle_count, self._last_cycle_time, len(filtered),
        )

    def _execute_signal(self, signal):
        # type: (AlgoSignal) -> Optional[dict]
        """Create a paper trade from an algo signal."""
        try:
            fees_entry = calculate_fees(
                signal.entry_price, signal.quantity, "BUY", "INTRADAY",
            )
            fees_exit_target = calculate_fees(
                signal.target, signal.quantity, "SELL", "INTRADAY",
            )
            fees_exit_sl = calculate_fees(
                signal.stop_loss, signal.quantity, "SELL", "INTRADAY",
            )

            capital_used = signal.entry_price * signal.quantity
            risk_amount = abs(signal.entry_price - signal.stop_loss) * signal.quantity

            trade_data = {
                "symbol": signal.symbol,
                "trade_type": "INTRADAY",
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "target": signal.target,
                "quantity": signal.quantity,
                "capital_used": round(capital_used, 2),
                "risk_amount": round(risk_amount, 2),
                "fees_entry": fees_entry["total"],
                "fees_exit_target": fees_exit_target["total"],
                "fees_exit_sl": fees_exit_sl["total"],
                "is_paper": 1,
                "order_status": "SIMULATED",
                "algo_id": signal.algo_id,
                "notes": "Algo: %s | %s" % (signal.algo_id, signal.reason),
                "entry_snapshot": json.dumps({
                    "algo_id": signal.algo_id,
                    "confidence": signal.confidence,
                    "reason": signal.reason,
                    "fee_breakeven": signal.fee_breakeven,
                    "expected_profit": signal.expected_profit,
                }),
            }

            trade = create_trade(trade_data)
            logger.info(
                "ALGO TRADE: %s -> %s qty=%d entry=%.2f sl=%.2f target=%.2f",
                signal.algo_id, signal.symbol, signal.quantity,
                signal.entry_price, signal.stop_loss, signal.target,
            )
            return trade
        except Exception:
            logger.exception("Failed to create algo trade for %s", signal.symbol)
            return None

    def _force_close_all(self):
        """Force-close all algo OPEN positions (intraday requirement)."""
        open_trades = list_trades(status="OPEN", is_paper=True)
        algo_trades = [t for t in open_trades if t.get("algo_id")]
        if not algo_trades:
            return

        symbols = list(set(t["symbol"] for t in algo_trades))
        ltp_map = self._fetch_ltp_batch(symbols)

        now = datetime.now(timezone.utc).isoformat()
        for trade in algo_trades:
            ltp = ltp_map.get(trade["symbol"])
            if not ltp or ltp <= 0:
                ltp = trade["entry_price"]  # fallback

            net_pnl, total_fees = compute_exit_pnl(
                trade["entry_price"], ltp, trade["quantity"], "INTRADAY",
            )
            status = "WON" if net_pnl > 0 else "LOST"
            update_trade(trade["id"], {
                "status": status,
                "exit_price": round(ltp, 2),
                "actual_pnl": net_pnl,
                "actual_fees": total_fees,
                "exit_date": now,
                "exit_trigger": "FORCE_CLOSE",
            })
            logger.info(
                "Force-closed algo trade #%s %s at %.2f (pnl=%.2f)",
                trade["id"], trade["symbol"], ltp, net_pnl,
            )
            self._log_signal(
                trade.get("algo_id", "unknown"), trade["symbol"],
                "FORCE_CLOSE", "Intraday force close at 15:15 IST",
                trade_id=trade["id"],
            )

    def _log_signal(self, algo_id, symbol, signal_type, reason, trade_id=None):
        # type: (str, str, str, str, Optional[int]) -> None
        """Log signal to both DB and in-memory ring buffer."""
        entry = {
            "algo_id": algo_id,
            "symbol": symbol,
            "signal_type": signal_type,
            "reason": reason,
            "trade_id": trade_id,
            "timestamp": time.time(),
        }
        self._signal_buffer.appendleft(entry)

        try:
            save_algo_signal({
                "algo_id": algo_id,
                "symbol": symbol,
                "signal_type": signal_type,
                "reason": reason,
                "trade_id": trade_id,
            })
        except Exception:
            logger.debug("Failed to persist algo signal to DB")

    def _fetch_ltp_batch(self, symbols):
        # type: (List[str]) -> Dict[str, float]
        """Fetch LTP for symbols via Groww API (same pattern as PositionMonitor)."""
        ltp_map = {}  # type: Dict[str, float]
        try:
            from main import get_groww_client
            groww = get_groww_client()

            for i in range(0, len(symbols), 50):
                batch = symbols[i:i + 50]
                exchange_syms = tuple("NSE_" + s for s in batch)
                try:
                    ltp_data = groww.get_ltp(
                        exchange_trading_symbols=exchange_syms, segment="CASH",
                    )
                    if isinstance(ltp_data, dict):
                        for key, val in ltp_data.items():
                            sym = key.replace("NSE_", "", 1)
                            if isinstance(val, dict):
                                price = float(val.get("ltp", 0))
                            else:
                                price = float(val) if val else 0
                            if price > 0:
                                ltp_map[sym] = price
                except Exception as e:
                    logger.warning("AlgoEngine LTP batch failed: %s", e)
        except Exception:
            logger.exception("AlgoEngine: failed to get Groww client for LTP")
        return ltp_map

    def _fetch_candles(self, symbol):
        # type: (str) -> List[dict]
        """Fetch 1-minute candles for a symbol."""
        try:
            from main import get_groww_client
            from symbol import fetch_candles
            groww = get_groww_client()
            return fetch_candles(groww, symbol, interval="1minute", days=1)
        except Exception as e:
            logger.warning("AlgoEngine: failed to fetch candles for %s: %s", symbol, e)
            return []
