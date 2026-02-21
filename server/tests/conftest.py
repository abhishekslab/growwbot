"""
Pytest configuration and shared fixtures.

Provides common fixtures for testing the GrowwBot application.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def mock_groww_client():
    """Mock Groww API client for testing."""
    client = MagicMock()
    client.get_ltp.return_value = {
        "NSE_RELIANCE": {"ltp": 2500.0},
        "NSE_TCS": {"ltp": 3500.0},
        "NSE_INFY": {"ltp": 1500.0},
    }
    client.get_holdings_for_user.return_value = {
        "holdings": [
            {
                "trading_symbol": "RELIANCE",
                "quantity": 10,
                "average_price": 2400.0,
                "tradable_exchanges": ["NSE"],
            },
            {
                "trading_symbol": "TCS",
                "quantity": 5,
                "average_price": 3400.0,
                "tradable_exchanges": ["NSE"],
            },
        ]
    }
    client.get_quote.return_value = {
        "symbol": "RELIANCE",
        "ltp": 2500.0,
        "change": 50.0,
        "change_percent": 2.0,
        "volume": 1000000,
        "day_high": 2550.0,
        "day_low": 2480.0,
        "day_open": 2500.0,
        "prev_close": 2450.0,
    }
    client.get_historical_candles.return_value = [
        {
            "time": 1704067200,
            "open": 2500.0,
            "high": 2550.0,
            "low": 2480.0,
            "close": 2520.0,
            "volume": 1000000,
        }
    ]
    client.place_order.return_value = {
        "success": True,
        "order_id": "TEST_ORDER_123",
        "message": "Order placed successfully",
    }
    client.get_order_status.return_value = {"status": "FILLED", "order_id": "TEST_ORDER_123"}
    return client


@pytest.fixture
def sample_candles():
    """Sample 1-minute candle data for testing."""
    base_time = int(datetime(2024, 1, 15, 9, 15, tzinfo=timezone.utc).timestamp())
    candles = []
    base_price = 2500.0

    for i in range(60):
        candles.append(
            {
                "time": base_time + (i * 60),
                "open": base_price + (i * 0.5),
                "high": base_price + (i * 0.5) + 10,
                "low": base_price + (i * 0.5) - 5,
                "close": base_price + (i * 0.5) + 5,
                "volume": 10000 + (i * 100),
            }
        )
        base_price += 0.5

    return candles


@pytest.fixture
def sample_trade():
    """Sample trade data for testing."""
    return {
        "id": 1,
        "symbol": "RELIANCE",
        "entry_price": 2500.0,
        "stop_loss": 2450.0,
        "target": 2600.0,
        "quantity": 10,
        "status": "OPEN",
        "trade_type": "INTRADAY",
        "is_paper": True,
        "algo_id": "momentum_scalp",
        "entry_date": "2024-01-15T09:30:00",
    }


@pytest.fixture
def sample_algo_signal():
    """Sample algo signal for testing."""
    return {
        "algo_id": "momentum_scalp",
        "symbol": "RELIANCE",
        "action": "BUY",
        "entry_price": 2500.0,
        "stop_loss": 2450.0,
        "target": 2600.0,
        "quantity": 10,
        "confidence": 0.75,
        "reason": "EMA 9/21 crossover, RSI 50, Vol 2.0x",
        "fee_breakeven": 0.5,
        "expected_profit": 500.0,
    }


@pytest.fixture
def sample_holdings():
    """Sample holdings data for testing."""
    return {
        "holdings": [
            {
                "symbol": "RELIANCE",
                "quantity": 10,
                "average_price": 2400.0,
                "ltp": 2500.0,
                "current_value": 25000.0,
                "invested_value": 24000.0,
                "pnl": 1000.0,
                "pnl_percentage": 4.17,
            },
            {
                "symbol": "TCS",
                "quantity": 5,
                "average_price": 3400.0,
                "ltp": 3500.0,
                "current_value": 17500.0,
                "invested_value": 17000.0,
                "pnl": 500.0,
                "pnl_percentage": 2.94,
            },
        ],
        "summary": {
            "total_current_value": 42500.0,
            "total_invested_value": 41000.0,
            "total_pnl": 1500.0,
            "total_pnl_percentage": 3.66,
        },
    }


@pytest.fixture
def sample_config():
    """Sample algo config for testing."""
    return {
        "capital": 100000,
        "risk_percent": 1,
        "max_positions_per_algo": 3,
        "max_total_positions": 6,
        "trading_start_ist": "09:30",
        "trading_end_ist": "15:00",
        "force_close_ist": "15:15",
        "momentum_scalp": {
            "ema_fast": 9,
            "ema_slow": 21,
            "rsi_min": 40,
            "rsi_max": 65,
            "volume_threshold": 1.5,
            "atr_target_mult": 1.5,
            "atr_sl_mult": 1.0,
        },
        "mean_reversion": {
            "rsi_max": 35,
            "volume_threshold": 2.0,
            "vwap_distance_atr_min": 1.0,
            "atr_sl_mult": 1.5,
        },
    }


@pytest.fixture
def mock_instrument_cache():
    """Mock instrument cache for symbol resolution."""
    return {
        "RELIANCE": {
            "trading_symbol": "RELIANCE",
            "exchange_token": "1234",
            "instrument_key": "NSE_RELIANCE",
        },
        "TCS": {
            "trading_symbol": "TCS",
            "exchange_token": "5678",
            "instrument_key": "NSE_TCS",
        },
    }


@pytest.fixture
def reset_groww_client():
    """Reset the groww client singleton after each test."""
    from infrastructure.groww_client import reset_groww_client

    yield
    reset_groww_client()


@pytest.fixture
def reset_cache():
    """Reset cache service after each test."""
    from services.cache_service import reset_cache_service

    yield
    reset_cache_service()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for testing."""
    import sqlite3

    db_path = tmp_path / "test_trades.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
