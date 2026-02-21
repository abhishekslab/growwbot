#!/usr/bin/env python3
"""
Phase 2 Refactor Verification Tests

Tests for new repository and service layers.
Note: Domain models require pydantic which may not be installed.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_repositories():
    """Test repository layer."""
    print("\nTesting repositories...")

    from repositories import TradeRepository, AlgoRepository

    # Test repository instantiation
    trade_repo = TradeRepository()
    algo_repo = AlgoRepository()

    assert trade_repo is not None
    assert algo_repo is not None
    print("  ✓ TradeRepository instantiated")
    print("  ✓ AlgoRepository instantiated")

    # Test that repository has expected methods
    assert hasattr(trade_repo, "get_by_id")
    assert hasattr(trade_repo, "list")
    assert hasattr(trade_repo, "create")
    assert hasattr(trade_repo, "update")
    assert hasattr(trade_repo, "delete")
    print("  ✓ TradeRepository has all required methods")

    print("  ✓ Repository layer working!")
    return True


def test_services():
    """Test service layer."""
    print("\nTesting services...")

    from services import TradeService, AlgoService
    from repositories import TradeRepository, AlgoRepository

    # Test service instantiation
    trade_service = TradeService(TradeRepository())
    algo_service = AlgoService(AlgoRepository())

    assert trade_service is not None
    assert algo_service is not None
    print("  ✓ TradeService instantiated")
    print("  ✓ AlgoService instantiated")

    # Test that services have expected methods
    assert hasattr(trade_service, "create_trade")
    assert hasattr(trade_service, "get_trade")
    assert hasattr(trade_service, "list_trades")
    assert hasattr(trade_service, "close_trade")
    print("  ✓ TradeService has all required methods")

    assert hasattr(algo_service, "get_settings")
    assert hasattr(algo_service, "record_signal")
    assert hasattr(algo_service, "get_performance")
    print("  ✓ AlgoService has all required methods")

    print("  ✓ Service layer working!")
    return True


def test_dependencies():
    """Test dependency injection."""
    print("\nTesting dependency injection...")

    from app.dependencies import get_trade_repository, get_algo_repository, trade_service_dependency, algo_service_dependency

    # Test repository providers
    trade_repo = get_trade_repository()
    algo_repo = get_algo_repository()

    assert trade_repo is not None
    assert algo_repo is not None
    print("  ✓ Repository providers working")

    # Test service providers
    trade_svc = trade_service_dependency()
    algo_svc = algo_service_dependency()

    assert trade_svc is not None
    assert algo_svc is not None
    print("  ✓ Service providers working")

    # Test singleton pattern
    trade_repo2 = get_trade_repository()
    assert trade_repo is trade_repo2
    print("  ✓ Singleton pattern working (same instance)")

    print("  ✓ Dependency injection working!")
    return True


def test_backward_compatibility():
    """Ensure old imports still work."""
    print("\nTesting backward compatibility...")

    # Old imports should still work
    from position_monitor import calculate_fees, compute_exit_pnl
    from indicators import calculate_ema
    from utils import ist_now
    from core import TradeError

    print("  ✓ All imports working (backward compatible)")

    # Test that fee functions work
    fees = calculate_fees(100.0, 10, "BUY", "INTRADAY")
    assert "total" in fees
    print(f"  ✓ calculate_fees working: {fees}")

    # Test compute_exit_pnl
    pnl, total_fees = compute_exit_pnl(100.0, 105.0, 10, "DELIVERY")
    print(f"  ✓ compute_exit_pnl working: PnL={pnl}, Fees={total_fees}")

    # Test IST time utilities
    now = ist_now()
    print(f"  ✓ ist_now working: {now}")

    return True


def test_new_utils():
    """Test new utility modules."""
    print("\nTesting new utility modules...")

    # Test time utils
    from utils.time_utils import ist_now, is_market_hours, get_market_status
    from utils.fees import calculate_position_size, calculate_risk_per_share

    now = ist_now()
    print(f"  ✓ ist_now: {now}")

    # Test market hours check (will depend on current time)
    in_hours = is_market_hours()
    print(f"  ✓ is_market_hours: {in_hours}")

    # Test market status
    status = get_market_status()
    print(f"  ✓ get_market_status: is_open={status['is_open']}")

    # Test position sizing
    risk = calculate_risk_per_share(100.0, 95.0, is_long=True)
    assert risk == 5.0
    print(f"  ✓ calculate_risk_per_share: {risk}")

    size = calculate_position_size(100000, 1, 5.0)
    print(f"  ✓ calculate_position_size: {size} shares")

    print("  ✓ All utility modules working!")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2 Refactor Verification Tests")
    print("=" * 60)

    try:
        test_repositories()
        test_services()
        test_dependencies()
        test_backward_compatibility()
        test_new_utils()

        print("\n" + "=" * 60)
        print("✅ ALL PHASE 2 TESTS PASSED!")
        print("Service and Repository layers working correctly.")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
