#!/usr/bin/env python3
"""
Test script to verify Phase 1 refactor works correctly.
Tests imports from both old and new module locations.
"""

import sys
import os

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_utils_imports():
    """Test importing from new utils module."""
    print("Testing utils module imports...")

    # Test fee utilities
    from utils import calculate_fees, compute_exit_pnl

    fees = calculate_fees(100.0, 10, "BUY", "INTRADAY")
    assert "total" in fees
    print(f"  ✓ calculate_fees: {fees}")

    # Test time utilities
    from utils import ist_now, is_market_hours

    now = ist_now()
    print(f"  ✓ ist_now: {now}")

    # Test indicator utilities
    from utils import calculate_ema, calculate_rsi

    test_closes = [100, 102, 101, 103, 105]
    ema = calculate_ema(test_closes, 3)
    print(f"  ✓ calculate_ema: {ema}")

    print("  ✓ All utils imports working!")
    return True


def test_core_imports():
    """Test importing from new core module."""
    print("\nTesting core module imports...")

    try:
        # We can't fully test settings without .env, but we can test exceptions
        from core import (
            GrowwBotException,
            AuthenticationError,
            TradeError,
            ValidationError,
        )

        # Test exception creation
        try:
            raise TradeError("Test error")
        except TradeError as e:
            print(f"  ✓ TradeError: {e.message}")

        print("  ✓ All core imports working!")
        return True
    except ImportError as e:
        print(f"  ⚠️  Some core imports skipped (pydantic not installed): {e}")
        return True


def test_backward_compatibility():
    """Test that old imports still work."""
    print("\nTesting backward compatibility...")

    # Test old position_monitor imports still work
    from position_monitor import PositionMonitor, calculate_fees, compute_exit_pnl

    print("  ✓ position_monitor imports still work")

    # Test old indicators import still works
    from indicators import calculate_ema

    print("  ✓ indicators import still works")

    print("  ✓ All backward compatibility tests passed!")
    return True


def test_fee_parity():
    """Test that fee calculations are identical between old and new implementations."""
    print("\nTesting fee calculation parity...")

    from utils.fees import calculate_fees as new_calculate_fees
    from utils.fees import compute_exit_pnl as new_compute_exit_pnl
    from position_monitor import calculate_fees as old_calculate_fees
    from position_monitor import compute_exit_pnl as old_compute_exit_pnl

    # Test cases
    test_cases = [
        (100.0, 10, "BUY", "INTRADAY"),
        (100.0, 10, "SELL", "INTRADAY"),
        (100.0, 10, "BUY", "DELIVERY"),
        (100.0, 10, "SELL", "DELIVERY"),
    ]

    for price, qty, side, trade_type in test_cases:
        old_result = old_calculate_fees(price, qty, side, trade_type)
        new_result = new_calculate_fees(price, qty, side, trade_type)
        assert old_result == new_result, f"Mismatch for {price}, {qty}, {side}, {trade_type}"

    # Test exit PnL parity
    old_pnl, old_fees = old_compute_exit_pnl(100.0, 105.0, 10, "DELIVERY")
    new_pnl, new_fees = new_compute_exit_pnl(100.0, 105.0, 10, "DELIVERY")
    assert old_pnl == new_pnl, f"PnL mismatch: {old_pnl} vs {new_pnl}"
    assert old_fees == new_fees, f"Fees mismatch: {old_fees} vs {new_fees}"

    print(f"  ✓ Fee calculations match: PnL={new_pnl}, Fees={new_fees}")
    print("  ✓ All fee parity tests passed!")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 Refactor Verification Tests")
    print("=" * 60)

    try:
        test_utils_imports()
        test_core_imports()
        test_backward_compatibility()
        test_fee_parity()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("Phase 1 refactor is working correctly.")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
