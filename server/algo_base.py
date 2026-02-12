"""
Base algorithm class and AlgoSignal dataclass.

All algo strategies inherit from BaseAlgorithm and implement evaluate().
"""

import math
from typing import Optional, List, Dict, Any

from position_monitor import calculate_fees


class AlgoSignal:
    """Signal returned by an algorithm's evaluate() method."""
    __slots__ = (
        "algo_id", "symbol", "action", "entry_price", "stop_loss", "target",
        "quantity", "confidence", "reason", "fee_breakeven", "expected_profit",
    )

    def __init__(
        self,
        algo_id,       # type: str
        symbol,        # type: str
        action,        # type: str  # "BUY" or "SKIP"
        entry_price,   # type: float
        stop_loss,     # type: float
        target,        # type: float
        quantity,      # type: int
        confidence,    # type: float  # 0-1
        reason,        # type: str
        fee_breakeven,  # type: float
        expected_profit,  # type: float
    ):
        self.algo_id = algo_id
        self.symbol = symbol
        self.action = action
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target = target
        self.quantity = quantity
        self.confidence = confidence
        self.reason = reason
        self.fee_breakeven = fee_breakeven
        self.expected_profit = expected_profit

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "algo_id": self.algo_id,
            "symbol": self.symbol,
            "action": self.action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "reason": self.reason,
            "fee_breakeven": self.fee_breakeven,
            "expected_profit": self.expected_profit,
        }


class BaseAlgorithm:
    """Abstract base class for trading algorithms."""

    ALGO_ID = ""       # type: str
    ALGO_NAME = ""     # type: str
    DESCRIPTION = ""   # type: str
    _effective_capital = None  # type: Optional[float]
    _risk_percent = None       # type: Optional[float]

    def set_runtime_params(self, effective_capital, risk_percent):
        # type: (float, float) -> None
        """Called by AlgoEngine before each cycle with per-algo settings."""
        self._effective_capital = effective_capital
        self._risk_percent = risk_percent

    def evaluate(self, symbol, candles, ltp, candidate_info):
        # type: (str, List[dict], float, dict) -> Optional[AlgoSignal]
        """Evaluate a symbol and return a signal or None.

        Must be overridden by subclasses.
        """
        raise NotImplementedError

    def should_skip_symbol(self, symbol, candidate_info, open_positions):
        # type: (str, dict, List[dict]) -> bool
        """Return True if this symbol should be skipped (e.g. already has a position)."""
        for pos in open_positions:
            if pos.get("symbol") == symbol and pos.get("algo_id") == self.ALGO_ID:
                return True
        return False

    def compute_fee_breakeven(self, entry_price, quantity, trade_type="INTRADAY"):
        # type: (float, int, str) -> float
        """Compute the minimum price move needed to cover fees (round-trip)."""
        if quantity <= 0 or entry_price <= 0:
            return float("inf")
        fees_buy = calculate_fees(entry_price, quantity, "BUY", trade_type)
        fees_sell = calculate_fees(entry_price, quantity, "SELL", trade_type)
        total_fees = fees_buy["total"] + fees_sell["total"]
        # Price move per share needed to cover fees
        return round(total_fees / quantity, 4)

    def compute_position_size(self, entry_price, stop_loss, capital, risk_pct):
        # type: (float, float, float, float) -> int
        """Risk-based position sizing: capital * risk% / risk-per-share."""
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            return 0
        max_risk = capital * (risk_pct / 100.0)
        qty = int(max_risk / risk_per_share)
        # Also cap by capital available
        max_qty_by_capital = int(capital / entry_price) if entry_price > 0 else 0
        return min(qty, max_qty_by_capital)
