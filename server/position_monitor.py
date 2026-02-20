"""
Background position monitor.

Polls LTP for all OPEN trades and auto-exits (MARKET SELL) when SL or target is breached.
Updates the trade ledger with exit details.
"""

import logging
import threading
import time
from datetime import datetime, timezone

from trades_db import list_trades, update_trade

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Python port of the fee calculator from client/lib/tradeCalculator.ts
# ---------------------------------------------------------------------------

DEFAULT_FEE_CONFIG = {
    "brokerage_per_order": 20,
    "stt_intraday_sell_rate": 0.00025,
    "stt_delivery_rate": 0.001,
    "exchange_txn_rate": 0.0000345,
    "sebi_rate": 0.000001,
    "stamp_duty_rate": 0.00003,
    "gst_rate": 0.18,
}


def calculate_fees(
    price,        # type: float
    qty,          # type: int
    side,         # type: str  # "BUY" or "SELL"
    trade_type,   # type: str  # "INTRADAY" or "DELIVERY"
    config=None,  # type: Optional[dict]
):
    # type: (...) -> dict
    if config is None:
        config = DEFAULT_FEE_CONFIG

    turnover = price * qty
    brokerage = min(config["brokerage_per_order"], turnover * 0.0003)

    if trade_type == "INTRADAY":
        stt = turnover * config["stt_intraday_sell_rate"] if side == "SELL" else 0
    else:
        stt = turnover * config["stt_delivery_rate"]

    exchange_txn = turnover * config["exchange_txn_rate"]
    sebi = turnover * config["sebi_rate"]
    stamp_duty = turnover * config["stamp_duty_rate"] if side == "BUY" else 0
    gst = (brokerage + exchange_txn + sebi) * config["gst_rate"]

    total = brokerage + stt + exchange_txn + sebi + stamp_duty + gst
    return {"total": round(total, 2)}


def compute_exit_pnl(entry_price, exit_price, quantity, trade_type="DELIVERY"):
    # type: (float, float, int, str) -> tuple
    """Return (net_pnl, total_fees) for an exit."""
    gross = (exit_price - entry_price) * quantity
    fees_entry = calculate_fees(entry_price, quantity, "BUY", trade_type)
    fees_exit = calculate_fees(exit_price, quantity, "SELL", trade_type)
    total_fees = fees_entry["total"] + fees_exit["total"]
    net = gross - total_fees
    return round(net, 2), round(total_fees, 2)


# ---------------------------------------------------------------------------
# Position monitor
# ---------------------------------------------------------------------------

class PositionMonitor:
    def __init__(self):
        self._running = False
        self._thread = None      # type: Optional[threading.Thread]
        self._base_interval = 5  # seconds
        self._poll_interval = 5  # current interval (increases on failures)
        self._max_interval = 60  # cap for backoff
        self._consecutive_failures = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("PositionMonitor started (poll every %ds)", self._poll_interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("PositionMonitor stopped")

    # ------------------------------------------------------------------
    def _monitor_loop(self):
        while self._running:
            try:
                open_trades = list_trades(status="OPEN")
                if not open_trades:
                    time.sleep(self._poll_interval)
                    continue

                symbols = list(set(t["symbol"] for t in open_trades))
                ltp_map = self._fetch_ltp_batch(symbols)

                if not ltp_map and symbols:
                    # All fetches failed — increase backoff
                    self._consecutive_failures += 1
                    self._poll_interval = min(
                        self._base_interval * (2 ** self._consecutive_failures),
                        self._max_interval,
                    )
                    logger.warning(
                        "PositionMonitor: %d consecutive failures, backing off to %ds",
                        self._consecutive_failures, self._poll_interval,
                    )
                else:
                    if self._consecutive_failures > 0:
                        logger.info(
                            "PositionMonitor: recovered after %d failures, resuming %ds interval",
                            self._consecutive_failures, self._base_interval,
                        )
                    self._consecutive_failures = 0
                    self._poll_interval = self._base_interval

                for trade in open_trades:
                    # Check if the buy order was rejected by the exchange
                    if self._check_order_rejected(trade):
                        continue  # trade already marked FAILED, skip LTP check

                    ltp = ltp_map.get(trade["symbol"])
                    if ltp is None or ltp <= 0:
                        continue
                    self._check_exit(trade, ltp)

            except Exception:
                logger.exception("PositionMonitor loop error")
                self._consecutive_failures += 1
                self._poll_interval = min(
                    self._base_interval * (2 ** self._consecutive_failures),
                    self._max_interval,
                )

            time.sleep(self._poll_interval)

    # ------------------------------------------------------------------
    def _check_order_rejected(self, trade):
        # type: (dict) -> bool
        """Check if the buy order for this trade was rejected by the exchange.
        Returns True if the trade was marked as FAILED (caller should skip it).
        """
        # Paper trades have no real order to verify
        if trade.get("is_paper"):
            return False

        order_id = trade.get("groww_order_id")
        if not order_id:
            return False

        # Only check trades whose order_status is still PLACED (not yet confirmed)
        if trade.get("order_status") not in (None, "PLACED"):
            return False

        try:
            from main import get_groww_client
            groww = get_groww_client()
            status_resp = groww.get_order_status(
                segment="CASH", groww_order_id=order_id,
            )
            order_status = ""
            if isinstance(status_resp, dict):
                order_status = status_resp.get("status", "").upper()

            if order_status in ("REJECTED", "CANCELLED"):
                reason = ""
                if isinstance(status_resp, dict):
                    reason = status_resp.get("rejection_reason", "") or status_resp.get("message", "")
                update_trade(trade["id"], {
                    "status": "FAILED",
                    "order_status": order_status,
                    "notes": "Order %s: %s" % (order_status.lower(), reason),
                })
                logger.warning(
                    "Trade #%s %s — order %s was %s: %s",
                    trade["id"], trade["symbol"], order_id, order_status, reason,
                )
                return True

            # If order is confirmed/executed, update order_status so we stop checking
            if order_status in ("EXECUTED", "TRADED", "COMPLETE", "FILLED"):
                update_trade(trade["id"], {"order_status": order_status})

        except Exception:
            logger.debug("Could not verify order status for trade #%s", trade["id"])

        return False

    # ------------------------------------------------------------------
    def _check_exit(self, trade, ltp):
        # type: (dict, float) -> None
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

        if triggered is None:
            return

        logger.info(
            "EXIT TRIGGERED: trade #%s %s %s — LTP=%.2f entry=%.2f sl=%.2f target=%.2f",
            trade["id"], trade["symbol"], triggered, ltp, entry, sl, target,
        )

        # Place MARKET SELL via Groww API (skip for paper trades)
        exit_price = ltp
        sell_succeeded = False
        if trade.get("is_paper"):
            sell_succeeded = True
            logger.info("Paper trade #%s auto-exit (%s) at %.2f", trade["id"], triggered, ltp)
        else:
            try:
                from main import get_groww_client
                groww = get_groww_client()
                order_result = groww.place_order(
                    validity="DAY",
                    exchange="NSE",
                    order_type="MARKET",
                    product="CNC",
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
                    "Failed to place SELL order for trade #%s %s — "
                    "keeping OPEN so monitor retries next cycle",
                    trade["id"], trade["symbol"],
                )

        if not sell_succeeded:
            return

        trade_type = trade.get("trade_type", "DELIVERY")
        net_pnl, total_fees = compute_exit_pnl(
            entry, exit_price, trade["quantity"], trade_type,
        )

        status = "WON" if triggered == "TARGET" else "LOST"
        now = datetime.now(timezone.utc).isoformat()

        update_trade(trade["id"], {
            "status": status,
            "exit_price": round(exit_price, 2),
            "actual_pnl": net_pnl,
            "actual_fees": total_fees,
            "exit_date": now,
            "exit_trigger": triggered,
        })
        logger.info(
            "Trade #%s closed as %s — exit=%.2f pnl=%.2f fees=%.2f",
            trade["id"], status, exit_price, net_pnl, total_fees,
        )

    # ------------------------------------------------------------------
    def _fetch_ltp_batch(self, symbols):
        # type: (list) -> Dict[str, float]
        """Fetch LTP for a list of trading symbols using the Groww API."""
        ltp_map = {}  # type: Dict[str, float]
        try:
            from main import get_groww_client
            groww = get_groww_client()

            # Batch in groups of 50
            for i in range(0, len(symbols), 50):
                batch = symbols[i:i + 50]
                exchange_syms = tuple("NSE_" + s for s in batch)

                # Try up to 2 attempts per batch
                for attempt in range(2):
                    try:
                        ltp_data = groww.get_ltp(
                            exchange_trading_symbols=exchange_syms, segment="CASH"
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
                        break  # success — no retry needed
                    except Exception:
                        if attempt == 0:
                            logger.warning("LTP batch fetch failed for %s, retrying in 2s", batch)
                            time.sleep(2)
                        else:
                            logger.exception("LTP batch fetch failed after retry for %s", batch)
        except Exception:
            logger.exception("Failed to get Groww client for LTP fetch")

        return ltp_map
