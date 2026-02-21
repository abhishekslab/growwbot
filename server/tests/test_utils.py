"""
Unit tests for utils module.
"""

import pytest
from utils.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_vwap,
    analyze_volume,
)
from utils.fees import calculate_fees, compute_exit_pnl
from utils.time_utils import ist_now, is_market_hours, get_market_status


class TestIndicators:
    def test_calculate_ema(self):
        closes = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        ema = calculate_ema(closes, period=5)
        assert len(ema) == len(closes)
        assert not (ema[-1] != ema[-1])  # Not NaN

    def test_calculate_rsi(self):
        candles = []
        base_price = 100.0
        for i in range(20):
            candles.append(
                {
                    "close": base_price + (i * 0.5),
                    "high": base_price + (i * 0.5) + 5,
                    "low": base_price + (i * 0.5) - 5,
                    "open": base_price + (i * 0.5),
                }
            )
            base_price += 0.5

        result = calculate_rsi(candles)
        assert "current" in result
        assert "zone" in result
        assert 0 <= result["current"] <= 100

    def test_calculate_atr(self, sample_candles):
        atr = calculate_atr(sample_candles)
        assert atr >= 0

    def test_calculate_vwap(self, sample_candles):
        ltp = 2500.0
        result = calculate_vwap(sample_candles, ltp)
        assert "vwap" in result
        assert "above_vwap" in result

    def test_analyze_volume(self, sample_candles):
        result = analyze_volume(sample_candles)
        assert "ratio" in result
        assert "average" in result
        assert result["ratio"] > 0


class TestFees:
    def test_calculate_fees_intraday(self):
        fees = calculate_fees(price=2500.0, qty=10, side="BUY", trade_type="INTRADAY")
        assert "total" in fees
        assert fees["total"] > 0

    def test_calculate_fees_delivery(self):
        fees = calculate_fees(price=2500.0, qty=10, side="BUY", trade_type="DELIVERY")
        assert "total" in fees
        assert fees["total"] > 0

    def test_compute_exit_pnl(self):
        pnl, fees = compute_exit_pnl(
            entry_price=2500.0,
            exit_price=2600.0,
            quantity=10,
            trade_type="INTRADAY",
        )
        assert pnl > 0
        assert fees > 0
        assert pnl > fees  # Should have profit after fees


class TestTimeUtils:
    def test_ist_now(self):
        now = ist_now()
        assert now is not None

    def test_is_market_hours(self):
        result = is_market_hours()
        assert isinstance(result, bool)

    def test_get_market_status(self):
        status = get_market_status()
        assert "is_open" in status
        assert "market_open" in status
        assert "market_close" in status
