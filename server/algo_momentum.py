"""
Momentum Scalping algorithm.

Entry criteria (ALL must be true):
- EMA 9 > EMA 21 (bullish) with recent crossover (last 3 candles)
- RSI 40-65 (healthy momentum, not overbought)
- Volume > 1.5x 20-period average
- Price above VWAP
- Time: 9:30-15:00 IST
- Target move (2.5x ATR) > fee breakeven + 150% margin

Exit: Target = entry + 2.5 ATR, SL = entry - 1.0 ATR (handled by PositionMonitor)
Time exit: 15 min max duration (handled by AlgoEngine)
"""

import json
import logging
import math
import os
import time

from algo_base import AlgoSignal, BaseAlgorithm
from indicators import analyze_volume, calculate_atr, calculate_ema, calculate_rsi, calculate_vwap

logger = logging.getLogger(__name__)

# #region agent log
_DBG_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cursor", "debug.log")
def _dbg(msg, data, hyp):
    try:
        os.makedirs(os.path.dirname(_DBG_LOG), exist_ok=True)
        with open(_DBG_LOG, "a") as _f:
            _f.write(json.dumps({"timestamp": int(time.time()*1000), "location": "algo_momentum.py", "hypothesisId": hyp, "message": msg, "data": data}) + "\n")
    except Exception:
        pass
# #endregion


class MomentumScalping(BaseAlgorithm):
    ALGO_ID = "momentum_scalp"
    ALGO_NAME = "Momentum Scalping"
    DESCRIPTION = "EMA crossover + RSI + volume confirmation on 1m candles"
    ALGO_VERSION = "1.0"

    def __init__(self, config):
        # type: (dict) -> None
        self.cfg = config.get("momentum_scalp", {})
        self.global_cfg = config

    def evaluate(self, symbol, candles, ltp, candidate_info):
        # type: (str, List[dict], float, dict) -> Optional[AlgoSignal]
        if len(candles) < 30:
            return None

        closes = [c["close"] for c in candles]
        ema_fast = self.cfg.get("ema_fast", 9)
        ema_slow = self.cfg.get("ema_slow", 21)

        ema9 = calculate_ema(closes, ema_fast)
        ema21 = calculate_ema(closes, ema_slow)

        # Check EMA 9 > EMA 21 (bullish trend)
        last_ema9 = ema9[-1]
        last_ema21 = ema21[-1]
        if math.isnan(last_ema9) or math.isnan(last_ema21):
            return None
        if last_ema9 <= last_ema21:
            # #region agent log
            if not hasattr(self, "_dbg_counts"):
                self._dbg_counts = {}
            self._dbg_counts["H-A_ema_bearish"] = self._dbg_counts.get("H-A_ema_bearish", 0) + 1
            # #endregion
            return None

        # Check recent crossover (last 3 candles)
        has_crossover = False
        for i in range(len(ema9) - 3, len(ema9)):
            if i < 1 or math.isnan(ema9[i]) or math.isnan(ema21[i]):
                continue
            if math.isnan(ema9[i - 1]) or math.isnan(ema21[i - 1]):
                continue
            if ema9[i] > ema21[i] and ema9[i - 1] <= ema21[i - 1]:
                has_crossover = True
                break
        if not has_crossover:
            # #region agent log
            if not hasattr(self, "_dbg_counts"):
                self._dbg_counts = {}
            self._dbg_counts["H-B_no_crossover"] = self._dbg_counts.get("H-B_no_crossover", 0) + 1
            # #endregion
            return None

        # RSI check
        rsi_result = calculate_rsi(candles)
        rsi = rsi_result["current"]
        rsi_min = self.cfg.get("rsi_min", 40)
        rsi_max = self.cfg.get("rsi_max", 65)
        if rsi < rsi_min or rsi > rsi_max:
            # #region agent log
            if not hasattr(self, "_dbg_counts"):
                self._dbg_counts = {}
            self._dbg_counts["H-C_rsi_oob"] = self._dbg_counts.get("H-C_rsi_oob", 0) + 1
            _dbg("RSI rejected", {"rsi": rsi, "min": rsi_min, "max": rsi_max, "candles": len(candles)}, "H-C")
            # #endregion
            return None

        # Volume check
        vol = analyze_volume(candles)
        vol_threshold = self.cfg.get("volume_threshold", 1.5)
        if vol["ratio"] < vol_threshold:
            # #region agent log
            if not hasattr(self, "_dbg_counts"):
                self._dbg_counts = {}
            self._dbg_counts["H-D_vol_low"] = self._dbg_counts.get("H-D_vol_low", 0) + 1
            _dbg("Volume rejected", {"ratio": vol["ratio"], "threshold": vol_threshold}, "H-D")
            # #endregion
            return None

        # VWAP check
        vwap_result = calculate_vwap(candles, ltp)
        if not vwap_result["above_vwap"]:
            # #region agent log
            if not hasattr(self, "_dbg_counts"):
                self._dbg_counts = {}
            self._dbg_counts["H-E_below_vwap"] = self._dbg_counts.get("H-E_below_vwap", 0) + 1
            _dbg("VWAP rejected", {"ltp": ltp, "vwap": vwap_result["vwap"]}, "H-E")
            # #endregion
            return None

        # ATR for target/SL
        atr = calculate_atr(candles)
        if atr <= 0:
            return None

        entry_price = ltp
        atr_target_mult = self.cfg.get("atr_target_mult", 1.5)
        atr_sl_mult = self.cfg.get("atr_sl_mult", 1.0)
        target = round(entry_price + atr * atr_target_mult, 2)
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
            # #region agent log
            if not hasattr(self, "_dbg_counts"):
                self._dbg_counts = {}
            self._dbg_counts["H-F_fee_margin"] = self._dbg_counts.get("H-F_fee_margin", 0) + 1
            _dbg("Fee margin rejected", {"target_move": target_move, "required_move": required_move, "fee_breakeven": fee_breakeven, "qty": quantity, "atr": atr}, "H-F")
            # #endregion
            return None

        expected_profit = round((target_move - fee_breakeven) * quantity, 2)

        reason = (
            "EMA %d/%d crossover, RSI %.1f, Vol %.1fx, Above VWAP %.2f, "
            "ATR %.2f, Target +%.2f (%.1fx ATR)"
            % (ema_fast, ema_slow, rsi, vol["ratio"], vwap_result["vwap"],
               atr, target_move, atr_target_mult)
        )

        return AlgoSignal(
            algo_id=self.ALGO_ID,
            symbol=symbol,
            action="BUY",
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            quantity=quantity,
            confidence=round(min(1.0, (rsi - 30) / 35 * vol["ratio"] / 2), 2),
            reason=reason,
            fee_breakeven=fee_breakeven,
            expected_profit=expected_profit,
        )

    def clone_with_config(self, overrides):
        # type: (dict) -> BaseAlgorithm
        """Create a fresh instance with merged config for backtesting."""
        from algo_momentum import MomentumScalping
        global_merged = dict(self.global_cfg)
        for k, v in overrides.items():
            if k != "momentum_scalp":
                global_merged[k] = v
        algo_overrides = overrides.get("momentum_scalp") or {}
        global_merged["momentum_scalp"] = dict(self.cfg, **algo_overrides)
        return MomentumScalping(global_merged)
