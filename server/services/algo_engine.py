"""
Algo trading engine — daemon thread that evaluates registered algorithms
on a 60-second cycle using Daily Picks as the symbol universe.

This module is the refactored version that imports from infrastructure
instead of main.py to avoid circular imports.
"""

import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from infrastructure.groww_client import get_groww_client
from strategies.base import BaseAlgorithm

try:
    from utils.fees import calculate_fees, compute_exit_pnl
except ImportError:
    from position_monitor import calculate_fees, compute_exit_pnl

try:
    from snapshot import load_snapshot
except ImportError:
    try:
        from infrastructure.snapshot_store import load_snapshot
    except ImportError:
        load_snapshot = None

try:
    from trades_db import (
        create_trade,
        get_algo_deployed_capital,
        get_algo_net_pnl,
        get_algo_settings,
        list_trades,
        save_algo_signal,
        update_trade,
        upsert_algo_settings,
    )
except ImportError:
    create_trade = None
    get_algo_deployed_capital = lambda x: 0
    get_algo_net_pnl = lambda x: 0
    get_algo_settings = lambda x: None
    list_trades = lambda: []
    save_algo_signal = lambda x: None
    update_trade = lambda x, y: None
    upsert_algo_settings = lambda x, y: None

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "algo_config.json")

_IST_OFFSET = timedelta(hours=5, minutes=30)


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH) as f:
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


def _ist_now() -> datetime:
    return datetime.now(timezone.utc) + _IST_OFFSET


def _parse_ist_time(time_str: str) -> tuple:
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


class AlgoEngine:
    """Main orchestrator daemon for algo trading."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._algos = {}
        self._algo_enabled = {}
        self._config = _load_config()
        self._cycle_interval = 60
        self._signal_buffer = deque(maxlen=200)
        self._last_cycle_time = 0.0
        self._cycle_count = 0
        self._candle_cache = {}
        self._candle_cache_ttl = 120
        self._candle_fail_counts = {}
        self._cycle_fetch_count = 0
        self._max_fetches_per_cycle = 8
        self._last_cycle_at = ""
        self._last_cycle_stats = {}
        self._market_status = "pre_market"

    def register_algo(self, algo: BaseAlgorithm) -> None:
        self._algos[algo.ALGO_ID] = algo
        if get_algo_settings:
            settings = get_algo_settings(algo.ALGO_ID)
            if settings:
                self._algo_enabled[algo.ALGO_ID] = bool(settings["enabled"])
            else:
                self._algo_enabled[algo.ALGO_ID] = True
                if upsert_algo_settings:
                    upsert_algo_settings(
                        algo.ALGO_ID,
                        {
                            "enabled": 1,
                            "capital": self._config.get("capital", 100000),
                            "risk_percent": self._config.get("risk_percent", 1),
                            "compounding": 0,
                        },
                    )
        else:
            self._algo_enabled[algo.ALGO_ID] = True
        logger.info(
            "Registered algo: %s (%s) enabled=%s",
            algo.ALGO_ID,
            algo.ALGO_NAME,
            self._algo_enabled[algo.ALGO_ID],
        )

    def start(self) -> None:
        if self._running:
            return
        self._config = _load_config()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(
            "AlgoEngine started with %d algorithms: %s",
            len(self._algos),
            ", ".join(self._algos.keys()),
        )

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=15)
        logger.info("AlgoEngine stopped")

    def start_algo(self, algo_id: str) -> bool:
        if algo_id in self._algos:
            self._algo_enabled[algo_id] = True
            if upsert_algo_settings:
                upsert_algo_settings(algo_id, {"enabled": 1})
            logger.info("Algo %s enabled", algo_id)
            return True
        return False

    def stop_algo(self, algo_id: str) -> bool:
        if algo_id in self._algos:
            self._algo_enabled[algo_id] = False
            if upsert_algo_settings:
                upsert_algo_settings(algo_id, {"enabled": 0})
            logger.info("Algo %s disabled", algo_id)
            return True
        return False

    def get_effective_capital(self, algo_id: str) -> float:
        settings = get_algo_settings(algo_id) if get_algo_settings else None
        if not settings:
            return self._config.get("capital", 100000)
        base = settings.get("capital", self._config.get("capital", 100000))
        compounding = settings.get("compounding", 0)
        if compounding:
            realized = get_algo_net_pnl(algo_id) if get_algo_net_pnl else 0
            return base + realized
        return base

    def get_runtime_params(self, algo_id: str) -> tuple:
        settings = get_algo_settings(algo_id) if get_algo_settings else None
        if not settings:
            return (
                self._config.get("capital", 100000),
                self._config.get("risk_percent", 1),
            )
        capital = settings.get("capital", self._config.get("capital", 100000))
        compounding = settings.get("compounding", 0)
        if compounding:
            realized = get_algo_net_pnl(algo_id) if get_algo_net_pnl else 0
            capital = capital + realized
        risk_pct = settings.get("risk_percent", self._config.get("risk_percent", 1))
        return capital, risk_pct

    def get_status(self) -> dict:
        now = _ist_now()
        hour, minute = now.hour, now.minute
        time_minutes = hour * 60 + minute

        start_h, start_m = _parse_ist_time(self._config.get("trading_start_ist", "09:30"))
        end_h, end_m = _parse_ist_time(self._config.get("trading_end_ist", "15:00"))
        close_h, close_m = _parse_ist_time(self._config.get("force_close_ist", "15:15"))
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        close_minutes = close_h * 60 + close_m

        if time_minutes < start_minutes:
            status = "pre_market"
        elif time_minutes < end_minutes:
            status = "trading"
        elif time_minutes < close_minutes:
            status = "post_market"
        else:
            status = "closed"

        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at,
            "market_status": status,
            "algos": {
                aid: {
                    "name": algo.ALGO_NAME,
                    "enabled": self._algo_enabled.get(aid, False),
                }
                for aid, algo in self._algos.items()
            },
        }

    def get_signals(self, limit: int = 50) -> List[dict]:
        return [s.to_dict() for s in list(self._signal_buffer)[-limit:]]

    def get_performance(self, algo_id: str = None) -> dict:
        if algo_id:
            return {
                "algo_id": algo_id,
                "net_pnl": get_algo_net_pnl(algo_id) if get_algo_net_pnl else 0,
                "deployed_capital": get_algo_deployed_capital(algo_id) if get_algo_deployed_capital else 0,
            }

        perf = {}
        for algo_id in self._algos:
            perf[algo_id] = {
                "net_pnl": get_algo_net_pnl(algo_id) if get_algo_net_pnl else 0,
                "deployed_capital": get_algo_deployed_capital(algo_id) if get_algo_deployed_capital else 0,
            }
        return perf

    def _is_trading_time(self) -> bool:
        now = _ist_now()
        hour, minute = now.hour, now.minute
        time_minutes = hour * 60 + minute

        start_h, start_m = _parse_ist_time(self._config.get("trading_start_ist", "09:30"))
        end_h, end_m = _parse_ist_time(self._config.get("trading_end_ist", "15:00"))
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        return start_minutes <= time_minutes < end_minutes

    def _loop(self) -> None:
        logger.info("AlgoEngine loop starting")
        while self._running:
            try:
                self._cycle()
            except Exception:
                logger.exception("AlgoEngine cycle failed")
            time.sleep(self._cycle_interval)
        logger.info("AlgoEngine loop exiting")

    def _cycle(self) -> None:
        self._cycle_fetch_count = 0
        now_ts = _ist_now().isoformat()
        self._last_cycle_at = now_ts
        self._cycle_count += 1

        if not self._is_trading_time():
            self._last_cycle_stats = {"skipped": "outside_trading_hours"}
            return

        snapshot = load_snapshot() if load_snapshot else None
        if not snapshot or not snapshot.get("candidates"):
            self._last_cycle_stats = {"skipped": "no_snapshot"}
            return

        candidates = snapshot.get("candidates", [])
        open_positions = list_trades() if list_trades else []
        open_positions = [t for t in open_positions if t.get("status") == "OPEN"]

        total_positions = len(open_positions)
        signals_created = 0

        for algo_id, algo in self._algos.items():
            if not self._algo_enabled.get(algo_id, False):
                continue

            algo_positions = [p for p in open_positions if p.get("algo_id") == algo_id]
            if len(algo_positions) >= self._config.get("max_positions_per_algo", 3):
                continue

            if total_positions >= self._config.get("max_total_positions", 6):
                break

            capital, risk_pct = self.get_runtime_params(algo_id)
            algo.set_runtime_params(capital, risk_pct)

            for candidate in candidates:
                symbol = candidate.get("symbol")
                if not symbol:
                    continue

                if algo.should_skip_symbol(symbol, candidate, open_positions):
                    continue

                try:
                    candles = self._fetch_candles(symbol)
                    if not candles or len(candles) < 30:
                        continue

                    ltp = self._fetch_ltp_for_symbol(symbol)
                    if ltp <= 0:
                        continue

                    signal = algo.evaluate(symbol, candles, ltp, candidate)
                    if signal and signal.action == "BUY":
                        self._signal_buffer.append(signal)
                        if save_algo_signal:
                            save_algo_signal(signal.to_dict())
                        signals_created += 1

                        # Determine paper mode - default to paper for safety
                        is_paper = candidate.get("is_paper", True)

                        if create_trade:
                            # Calculate capital used and risk amount
                            capital_used = signal.entry_price * signal.quantity
                            risk_per_share = abs(signal.entry_price - signal.stop_loss)
                            risk_amount = risk_per_share * signal.quantity

                            trade_data = {
                                "symbol": signal.symbol,
                                "entry_price": signal.entry_price,
                                "stop_loss": signal.stop_loss,
                                "target": signal.target,
                                "quantity": signal.quantity,
                                "trade_type": "INTRADAY",
                                "is_paper": is_paper,
                                "algo_id": signal.algo_id,
                                "capital_used": capital_used,
                                "risk_amount": risk_amount,
                            }
                            create_trade(trade_data)
                        open_positions.append(
                            {
                                "symbol": signal.symbol,
                                "algo_id": signal.algo_id,
                            }
                        )
                        total_positions += 1

                except Exception:
                    logger.exception("Error evaluating %s with %s", symbol, algo_id)

        self._last_cycle_stats = {
            "candidates": len(candidates),
            "signals": signals_created,
            "open_positions": total_positions,
        }
        logger.info(
            "AlgoEngine cycle %d: %d candidates, %d signals, %d positions",
            self._cycle_count,
            len(candidates),
            signals_created,
            total_positions,
        )

    def _fetch_ltp_for_symbol(self, symbol: str) -> float:
        try:
            groww = get_groww_client()
            ltp_data = groww.get_ltp(("NSE_" + symbol,))
            val = ltp_data.get("NSE_" + symbol)
            if isinstance(val, dict):
                return float(val.get("ltp", 0))
            return float(val) if val else 0
        except Exception as e:
            logger.warning("Failed to fetch LTP for %s: %s", symbol, e)
            return 0

    def _fetch_ltp_batch(self, symbols: List[str]) -> Dict[str, float]:
        ltp_map = {}
        try:
            groww = get_groww_client()

            for i in range(0, len(symbols), 50):
                batch = symbols[i : i + 50]
                exchange_syms = tuple("NSE_" + s for s in batch)
                try:
                    ltp_data = groww.get_ltp(exchange_trading_symbols=exchange_syms, segment="CASH")
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

    def _fetch_candles(self, symbol: str) -> List[dict]:
        now = time.monotonic()

        cached = self._candle_cache.get(symbol)
        if cached and cached[1] > now:
            return cached[0]

        if self._cycle_fetch_count >= self._max_fetches_per_cycle:
            return []

        try:
            groww = get_groww_client()

            try:
                from symbol import fetch_candles as _fetch_candles

                candles = _fetch_candles(groww, symbol, interval="1minute", days=1)
            except ImportError:
                try:
                    from infrastructure.groww_client import fetch_candles as _fetch_candles

                    candles = _fetch_candles(symbol, "", "", interval="1minute")
                except Exception:
                    candles = []

            self._cycle_fetch_count += 1
            self._candle_cache[symbol] = (candles, now + self._candle_cache_ttl)
            self._candle_fail_counts.pop(symbol, None)
            time.sleep(0.4)
            return candles
        except Exception as e:
            self._cycle_fetch_count += 1
            logger.warning("AlgoEngine: failed to fetch candles for %s: %s", symbol, e)

            fails = self._candle_fail_counts.get(symbol, 0) + 1
            self._candle_fail_counts[symbol] = fails
            backoff = min(120 * (2 ** (fails - 1)), 600)
            self._candle_cache[symbol] = ([], now + backoff)
            return []

    def _prune_candle_cache(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._candle_cache.items() if v[1] <= now]
        for k in expired:
            del self._candle_cache[k]


_engine_instance = None


def get_algo_engine() -> AlgoEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AlgoEngine()
    return _engine_instance
