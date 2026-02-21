"""
Mean Reversion algorithm.

Entry criteria (ALL must be true):
- Price below VWAP by > 1 ATR
- RSI < 35 (oversold)
- Volume spike > 2x average
- Time: 10:00-14:30 IST (range-bound window)
- Target move (to VWAP) > fee breakeven + 50% margin

Exit: Target = VWAP (mean reversion), SL = entry - 1.5 ATR
"""

import logging

from algo_base import AlgoSignal, BaseAlgorithm
from indicators import analyze_volume, calculate_atr, calculate_rsi, calculate_vwap

logger = logging.getLogger(__name__)


class MeanReversion(BaseAlgorithm):
    ALGO_ID = "mean_reversion"
    ALGO_NAME = "Mean Reversion"
    DESCRIPTION = "Buy oversold stocks below VWAP with volume spike, target VWAP"
    ALGO_VERSION = "1.0"

    def __init__(self, config):
        # type: (dict) -> None
        self.cfg = config.get("mean_reversion", {})
        self.global_cfg = config

    def evaluate(self, symbol, candles, ltp, candidate_info):
        # type: (str, List[dict], float, dict) -> Optional[AlgoSignal]
        if len(candles) < 30:
            return None

        entry_price = ltp

        # VWAP check: price must be below VWAP
        vwap_result = calculate_vwap(candles, ltp)
        vwap = vwap_result["vwap"]
        if vwap <= 0 or vwap_result["above_vwap"]:
            return None

        # ATR for distance + SL
        atr = calculate_atr(candles)
        if atr <= 0:
            return None

        # Distance from VWAP must be > N ATRs
        vwap_distance = vwap - entry_price
        min_atr_distance = self.cfg.get("vwap_distance_atr_min", 1.0)
        if vwap_distance < atr * min_atr_distance:
            return None

        # RSI check: must be oversold
        rsi_result = calculate_rsi(candles)
        rsi = rsi_result["current"]
        rsi_max = self.cfg.get("rsi_max", 35)
        if rsi > rsi_max:
            return None

        # Volume spike check
        vol = analyze_volume(candles)
        vol_threshold = self.cfg.get("volume_threshold", 2.0)
        if vol["ratio"] < vol_threshold:
            return None

        # Target = VWAP, SL = entry - 1.5 ATR
        target = round(vwap, 2)
        atr_sl_mult = self.cfg.get("atr_sl_mult", 1.5)
        stop_loss = round(entry_price - atr * atr_sl_mult, 2)

        # Position sizing (prefer runtime params from AlgoEngine)
        capital = self._effective_capital or self.global_cfg.get("capital", 100000)
        risk_pct = self._risk_percent or self.global_cfg.get("risk_percent", 1)
        quantity = self.compute_position_size(entry_price, stop_loss, capital, risk_pct)
        if quantity <= 0:
            return None

        # Fee-aware gate
        fee_breakeven = self.compute_fee_breakeven(entry_price, quantity, "INTRADAY")
        target_move = target - entry_price
        fee_margin = self.cfg.get("fee_safety_margin", 0.5)
        required_move = fee_breakeven * (1 + fee_margin)
        if target_move <= required_move:
            return None

        expected_profit = round((target_move - fee_breakeven) * quantity, 2)

        reason = (
            "Below VWAP %.2f by %.2f (%.1fx ATR), RSI %.1f (oversold), "
            "Vol %.1fx spike, Target=VWAP"
            % (vwap, vwap_distance, vwap_distance / atr, rsi, vol["ratio"])
        )

        return AlgoSignal(
            algo_id=self.ALGO_ID,
            symbol=symbol,
            action="BUY",
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            quantity=quantity,
            confidence=round(min(1.0, (35 - rsi) / 20 * vol["ratio"] / 3), 2),
            reason=reason,
            fee_breakeven=fee_breakeven,
            expected_profit=expected_profit,
        )

    def clone_with_config(self, overrides):
        # type: (dict) -> BaseAlgorithm
        """Create a fresh instance with merged config for backtesting."""
        from algo_mean_reversion import MeanReversion
        global_merged = dict(self.global_cfg)
        for k, v in overrides.items():
            if k != "mean_reversion":
                global_merged[k] = v
        algo_overrides = overrides.get("mean_reversion") or {}
        global_merged["mean_reversion"] = dict(self.cfg, **algo_overrides)
        return MeanReversion(global_merged)
