"""
Background position monitor.

Polls LTP for all OPEN trades and auto-exits (MARKET SELL) when SL or target is breached.
Updates the trade ledger with exit details.

This is the refactored version that imports from infrastructure instead of main.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from infrastructure.groww_client import get_groww_client

try:
    from utils.fees import calculate_fees, compute_exit_pnl
except ImportError:
    from position_monitor import calculate_fees, compute_exit_pnl

try:
    from trades_db import list_trades, update_trade
except ImportError:
    list_trades = None
    update_trade = None

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Background monitor for open positions."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._base_interval = 5
        self._poll_interval = 5
        self._max_interval = 60
        self._consecutive_failures = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("PositionMonitor started (poll every %ds)", self._poll_interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("PositionMonitor stopped")

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                if list_trades:
                    open_trades = list_trades(status="OPEN")
                else:
                    open_trades = []

                if not open_trades:
                    time.sleep(self._poll_interval)
                    continue

                symbols = list(set(t["symbol"] for t in open_trades))
                ltp_map = self._fetch_ltp_batch(symbols)

                if not ltp_map and symbols:
                    self._consecutive_failures += 1
                    self._poll_interval = min(
                        self._base_interval * (2**self._consecutive_failures),
                        self._max_interval,
                    )
                    logger.warning(
                        "PositionMonitor: %d consecutive failures, backing off to %ds",
                        self._consecutive_failures,
                        self._poll_interval,
                    )
                else:
                    if self._consecutive_failures > 0:
                        logger.info(
                            "PositionMonitor: recovered after %d failures, resuming %ds interval",
                            self._consecutive_failures,
                            self._base_interval,
                        )
                    self._consecutive_failures = 0
                    self._poll_interval = self._base_interval

                for trade in open_trades:
                    if self._check_order_rejected(trade):
                        continue

                    ltp = ltp_map.get(trade["symbol"])
                    if ltp is None or ltp <= 0:
                        continue
                    self._check_exit(trade, ltp)

            except Exception:
                logger.exception("PositionMonitor loop error")
                self._consecutive_failures += 1
                self._poll_interval = min(
                    self._base_interval * (2**self._consecutive_failures),
                    self._max_interval,
                )

            time.sleep(self._poll_interval)

    def _check_order_rejected(self, trade: dict) -> bool:
        if trade.get("is_paper"):
            return False

        order_id = trade.get("groww_order_id")
        if not order_id:
            return False

        if trade.get("order_status") not in (None, "PLACED"):
            return False

        try:
            groww = get_groww_client()
            status_resp = groww.get_order_status(segment="CASH", groww_order_id=order_id)
            order_status = ""
            if isinstance(status_resp, dict):
                order_status = status_resp.get("status", "").upper()

            if order_status in ("REJECTED", "CANCELLED"):
                reason = ""
                if isinstance(status_resp, dict):
                    reason = status_resp.get("rejection_reason", "") or status_resp.get("message", "")
                if update_trade:
                    update_trade(
                        trade["id"],
                        {
                            "status": "FAILED",
                            "order_status": order_status,
                            "notes": "Order %s: %s" % (order_status.lower(), reason),
                        },
                    )
                logger.warning(
                    "Trade #%s %s — order %s was %s: %s",
                    trade["id"],
                    trade["symbol"],
                    order_id,
                    order_status,
                    reason,
                )
                return True

            if order_status in ("EXECUTED", "TRADED", "COMPLETE", "FILLED"):
                if update_trade:
                    update_trade(trade["id"], {"order_status": order_status})

        except Exception:
            logger.debug("Could not verify order status for trade #%s", trade["id"])

        return False

    def _check_exit(self, trade: dict, ltp: float) -> None:
        entry = trade["entry_price"]
        sl = trade["stop_loss"]
        target = trade["target"]
        is_long = entry > sl

        triggered = None
        if is_long:
            if ltp <= sl:
                triggered = "SL"
            elif ltp >= target:
                triggered = "TARGET"
        else:
            if ltp >= sl:
                triggered = "SL"
            elif ltp <= target:
                triggered = "TARGET"

        # Check time-based exit (max trade duration)
        entry_time_str = trade.get("entry_time")
        max_duration = trade.get("max_trade_duration_minutes", 15)  # Default 15 minutes
        if triggered is None and entry_time_str:
            try:
                entry_time = datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
                elapsed_minutes = (datetime.now(timezone.utc) - entry_time).total_seconds() / 60
                if elapsed_minutes >= max_duration:
                    triggered = "TIME_EXIT"
                    logger.info(
                        "TIME EXIT: trade #%s %s — elapsed %.1f min (max %d min)", trade["id"], trade["symbol"], elapsed_minutes, max_duration
                    )
            except Exception as e:
                logger.warning("Failed to parse entry_time for trade #%s: %s", trade["id"], e)

        if triggered is None:
            return

        logger.info(
            "EXIT TRIGGERED: trade #%s %s %s — LTP=%.2f entry=%.2f sl=%.2f target=%.2f",
            trade["id"],
            trade["symbol"],
            triggered,
            ltp,
            entry,
            sl,
            target,
        )

        exit_price = ltp
        sell_succeeded = False
        if trade.get("is_paper"):
            sell_succeeded = True
            logger.info("Paper trade #%s auto-exit (%s) at %.2f", trade["id"], triggered, ltp)
        else:
            try:
                groww = get_groww_client()
                # Determine product type based on trade_type
                trade_type = trade.get("trade_type", "DELIVERY")
                product = "MIS" if trade_type == "INTRADAY" else "CNC"

                order_result = groww.place_order(
                    validity="DAY",
                    exchange="NSE",
                    order_type="MARKET",
                    product=product,
                    quantity=trade["quantity"],
                    segment="CASH",
                    trading_symbol=trade["symbol"],
                    transaction_type="SELL",
                    price=0,
                )
                sell_succeeded = True
                logger.info("SELL order placed for trade #%s: %s", trade["id"], order_result)
            except Exception:
                logger.exception(
                    "Failed to place SELL order for trade #%s %s — keeping OPEN so monitor retries next cycle",
                    trade["id"],
                    trade["symbol"],
                )

        if not sell_succeeded:
            return

        trade_type = trade.get("trade_type", "DELIVERY")
        net_pnl, total_fees = compute_exit_pnl(entry, exit_price, trade["quantity"], trade_type)

        status = "WON" if triggered == "TARGET" else "LOST"
        now = datetime.now(timezone.utc).isoformat()

        if update_trade:
            update_trade(
                trade["id"],
                {
                    "status": status,
                    "exit_price": round(exit_price, 2),
                    "exit_time": now,
                    "pnl": round(net_pnl, 2),
                    "fees": round(total_fees, 2),
                },
            )

        logger.info(
            "Trade #%s %s — %s at %.2f, PnL=%.2f, fees=%.2f",
            trade["id"],
            trade["symbol"],
            status,
            exit_price,
            net_pnl,
            total_fees,
        )

    def _fetch_ltp_batch(self, symbols: List[str]) -> Dict[str, float]:
        ltp_map = {}
        if not symbols:
            return ltp_map

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
                    logger.warning("PositionMonitor LTP batch failed: %s", e)
        except Exception:
            logger.exception("PositionMonitor: failed to get Groww client for LTP")

        return ltp_map


_monitor_instance = None


def get_position_monitor() -> PositionMonitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PositionMonitor()
    return _monitor_instance
