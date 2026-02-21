#!/usr/bin/env python3
"""
Phase 4 Integration Tests

Tests for the complete integrated application with new and legacy routes.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all imports work correctly."""
    print("\nTesting all imports...")

    # Test main imports
    from main import app

    print("  ✓ main imports successfully")

    # Test new routes
    from app.api import trades, algos, system

    print("  ✓ New API routes importable")

    # Test legacy routes
    from app.legacy_routes import router as legacy_router

    print("  ✓ Legacy routes importable")

    # Test FastAPI app
    assert app is not None
    print("  ✓ FastAPI app created")

    return True


def test_routes_registered():
    """Test that all routes are registered."""
    print("\nTesting route registration...")

    from main import app

    # Get all routes
    routes = app.routes
    route_paths = [r.path for r in routes if hasattr(r, "path")]

    # Check for new routes
    assert any("/api/trades" in p for p in route_paths), "Trades routes not found"
    assert any("/api/algos" in p for p in route_paths), "Algos routes not found"
    assert any("/api/system" in p for p in route_paths), "System routes not found"
    print("  ✓ New routes registered")

    # Check for legacy routes
    assert any("/api/v1" in p for p in route_paths), "Legacy routes not found"
    print("  ✓ Legacy routes registered")

    # Check for root endpoints
    assert "/" in route_paths, "Root endpoint not found"
    assert "/api/info" in route_paths, "API info endpoint not found"
    print("  ✓ Root endpoints registered")

    total_routes = len([r for r in routes if hasattr(r, "path")])
    print(f"  ✓ Total routes: {total_routes}")

    return True


def test_domain_models():
    """Test domain models with pydantic v2."""
    print("\nTesting domain models...")

    from domain.models import TradeCreate, Trade, TradeUpdate

    # Test TradeCreate
    trade_create = TradeCreate(
        symbol="RELIANCE",
        trade_type="INTRADAY",
        entry_price=2500.0,
        stop_loss=2480.0,
        target=2550.0,
        quantity=10,
        capital_used=25000.0,
        risk_amount=200.0,
        is_paper=True,
    )
    assert trade_create.symbol == "RELIANCE"
    print("  ✓ TradeCreate model works")

    # Test TradeUpdate
    update = TradeUpdate(status="CLOSED", exit_price=2540.0)
    assert update.status == "CLOSED"
    print("  ✓ TradeUpdate model works")

    return True


def test_services_with_pydantic():
    """Test services with pydantic models enabled."""
    print("\nTesting services with pydantic...")

    from services import TradeService, AlgoService
    from repositories import TradeRepository, AlgoRepository
    from domain.models import TradeCreate

    # Create services
    trade_service = TradeService(TradeRepository())
    algo_service = AlgoService(AlgoRepository())

    print("  ✓ Services initialized with pydantic")

    # Test that USE_PYDANTIC is True
    from services.trade_service import USE_PYDANTIC

    assert USE_PYDANTIC == True, "Pydantic should be enabled"
    print("  ✓ Pydantic mode enabled in services")

    return True


def test_logging_integration():
    """Test logging integration."""
    print("\nTesting logging integration...")

    from core.logging_config import get_logger, log_request, log_response, log_error

    # Test logger
    test_logger = get_logger("test.integration")
    test_logger.info("Integration test log message")
    print("  ✓ Logging works in integrated app")

    return True


def test_backward_compatibility():
    """Test backward compatibility with old imports."""
    print("\nTesting backward compatibility...")

    # Old imports still work
    from position_monitor import calculate_fees, compute_exit_pnl
    from indicators import calculate_ema, calculate_rsi
    from utils import ist_now, calculate_position_size
    from core import TradeError, get_logger

    # Test old functionality
    fees = calculate_fees(100.0, 10, "BUY", "INTRADAY")
    assert "total" in fees
    print("  ✓ Old fee calculations work")

    pnl, total_fees = compute_exit_pnl(100.0, 105.0, 10, "DELIVERY")
    assert pnl > 0
    print("  ✓ Old PnL calculations work")

    ema = calculate_ema([100, 102, 101, 103, 105], 3)
    assert len(ema) == 5
    print("  ✓ Old indicators work")

    return True


def test_fastapi_app_structure():
    """Test FastAPI app structure."""
    print("\nTesting FastAPI app structure...")

    from main import app

    # Check middleware
    assert len(app.user_middleware) > 0, "No middleware configured"
    print(f"  ✓ Middleware configured: {len(app.user_middleware)} middleware(s)")

    # Check exception handlers
    assert len(app.exception_handlers) > 0, "No exception handlers configured"
    print(f"  ✓ Exception handlers configured: {len(app.exception_handlers)} handler(s)")

    # Check CORS
    cors_middleware = [m for m in app.user_middleware if "CORSMiddleware" in str(m.cls)]
    assert len(cors_middleware) > 0, "CORS middleware not found"
    print("  ✓ CORS middleware configured")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 4 Integration Tests")
    print("=" * 60)

    try:
        test_imports()
        test_routes_registered()
        test_domain_models()
        test_services_with_pydantic()
        test_logging_integration()
        test_backward_compatibility()
        test_fastapi_app_structure()

        print("\n" + "=" * 60)
        print("✅ ALL PHASE 4 TESTS PASSED!")
        print("Integration complete - new architecture ready!")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
