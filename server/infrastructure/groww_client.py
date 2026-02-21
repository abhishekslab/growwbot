"""
Infrastructure layer - External API clients and services.

This module provides abstractions for external services (Groww API, cache, news)
to improve testability and reduce coupling.
"""

from typing import Any, Dict, List, Optional
import logging
import os
import time

from core.logging_config import get_logger
from infrastructure.auth import (
    _load_token,
    _save_token,
    get_cached_client,
    set_cached_client,
    get_auth_fail_time,
    set_auth_fail_time,
    get_auth_lock,
    get_token_ttl,
    get_auth_cooldown,
)

logger = get_logger("infrastructure")


class GrowwClientBase:
    """Abstract base class for Groww API client."""

    def get_access_token(self, api_key: str, secret: str) -> str:
        """Get access token from API credentials."""
        raise NotImplementedError

    def get_holdings_for_user(self) -> List[Dict]:
        """Get user holdings."""
        raise NotImplementedError

    def get_ltp(self, exchange_trading_symbols: tuple, segment: str = "CASH") -> Dict:
        """Get last traded price for symbols."""
        raise NotImplementedError

    def get_ohlc(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> Dict:
        """Get OHLC data for a symbol."""
        raise NotImplementedError

    def get_quote(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> Dict:
        """Get quote for a symbol."""
        raise NotImplementedError

    def get_historical_candles(self, symbol: str, exchange: str, from_date: str, to_date: str, interval: str = "1d") -> List[Dict]:
        """Get historical candle data."""
        raise NotImplementedError

    def get_all_instruments(self) -> List[Dict]:
        """Get all available instruments."""
        raise NotImplementedError

    def place_order(self, **kwargs) -> Dict:
        """Place a trading order."""
        raise NotImplementedError

    def get_order_status(self, segment: str, groww_order_id: str) -> Dict:
        """Get order status."""
        raise NotImplementedError


def _create_groww_client() -> Optional[object]:
    """Create a new Groww client, handling authentication."""
    from growwapi import GrowwAPI

    now = time.time()

    saved_token, saved_time = _load_token()
    if saved_token:
        logger.info("Loaded persisted token from disk (age %.0fs)", now - saved_time)
        client = GrowwAPI(saved_token)
        set_cached_client(client)
        return client

    auth_fail_time = get_auth_fail_time()
    if auth_fail_time and (now - auth_fail_time) < get_auth_cooldown():
        wait = int(get_auth_cooldown() - (now - auth_fail_time))
        logger.warning("Auth rate-limited. Retry in %ds", wait)
        return None

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        logger.warning("API_KEY and API_SECRET not set")
        return None

    try:
        access_token = GrowwAPI.get_access_token(api_key, secret=api_secret)
        client = GrowwAPI(access_token)
        set_cached_client(client)
        _save_token(access_token)
        logger.info("Groww auth successful, token persisted to disk")
        return client
    except Exception as e:
        logger.warning("Auth failed: %s", e)
        set_auth_fail_time(time.time())
        cached = get_cached_client()
        if cached:
            logger.warning("Returning stale client")
            return cached
        return None


class GrowwClient(GrowwClientBase):
    """Production Groww API client implementation with auth handling."""

    def __init__(self, access_token: str = None):
        self._client = None
        if access_token:
            from growwapi import GrowwAPI

            self._client = GrowwAPI(access_token)
        logger.info("GrowwClient initialized")

    def _ensure_client(self) -> object:
        """Ensure client is initialized, getting a cached or new one."""
        if self._client is not None:
            return self._client

        cached = get_cached_client()
        if cached:
            self._client = cached
            return self._client

        self._client = _create_groww_client()
        return self._client

    def get_access_token(self, api_key: str, secret: str) -> str:
        from growwapi import GrowwAPI

        return GrowwAPI.get_access_token(api_key, secret=secret)

    def get_holdings_for_user(self) -> List[Dict]:
        client = self._ensure_client()
        if client is None:
            return {"holdings": [], "error": "Authentication not available"}
        return client.get_holdings_for_user()

    def get_ltp(self, exchange_trading_symbols: tuple, segment: str = "CASH") -> Dict:
        client = self._ensure_client()
        if client is None:
            return {}
        return client.get_ltp(exchange_trading_symbols=exchange_trading_symbols, segment=segment)

    def get_ohlc(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> Dict:
        client = self._ensure_client()
        if client is None:
            return {}
        return client.get_ohlc(symbol, exchange, segment)

    def get_quote(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> Dict:
        client = self._ensure_client()
        if client is None:
            return {}
        return client.get_quote(symbol, exchange, segment)

    def get_historical_candles(self, symbol: str, exchange: str, from_date: str, to_date: str, interval: str = "1d") -> List[Dict]:
        client = self._ensure_client()
        if client is None:
            return []
        # Map to GrowwAPI parameter names
        return client.get_historical_candles(
            exchange=exchange,
            segment="CASH",
            groww_symbol=symbol,
            start_time=from_date,
            end_time=to_date,
            candle_interval=interval,
        )

    def get_all_instruments(self) -> List[Dict]:
        client = self._ensure_client()
        if client is None:
            return []
        return client.get_all_instruments()

    def place_order(self, **kwargs) -> Dict:
        client = self._ensure_client()
        if client is None:
            return {"success": False, "error": "Authentication not available"}
        return client.place_order(**kwargs)

    def get_order_status(self, segment: str, groww_order_id: str) -> Dict:
        client = self._ensure_client()
        if client is None:
            return {"status": "UNKNOWN"}
        return client.get_order_status(segment=segment, groww_order_id=groww_order_id)


class MockGrowwClient(GrowwClientBase):
    """Mock Groww client for testing."""

    def __init__(self, mock_data: Dict[str, Any] = None):
        self._mock_data = mock_data or {}
        logger.info("MockGrowwClient initialized")

    def get_access_token(self, api_key: str, secret: str) -> str:
        return "mock_token_12345"

    def get_holdings_for_user(self) -> List[Dict]:
        return self._mock_data.get("holdings", [{"symbol": "RELIANCE", "quantity": 10, "avg_price": 2500.0}])

    def get_ltp(self, exchange_trading_symbols: tuple, segment: str = "CASH") -> Dict:
        result = {}
        for sym in exchange_trading_symbols:
            symbol = sym.replace("NSE_", "")
            result[sym] = {"ltp": self._mock_data.get("ltp", {}).get(symbol, 2500.0)}
        return result

    def get_ohlc(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> Dict:
        return self._mock_data.get("ohlc", {"symbol": symbol, "open": 2500.0, "high": 2550.0, "low": 2480.0, "close": 2520.0, "volume": 1000000})

    def get_quote(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> Dict:
        quote_data = self._mock_data.get("quote", {})
        if isinstance(quote_data, dict) and symbol in quote_data:
            return quote_data[symbol]
        return quote_data or {
            "symbol": symbol,
            "ltp": 2520.0,
            "change": 20.0,
            "change_percent": 0.8,
            "volume": 1000000,
            "day_high": 2550.0,
            "day_low": 2480.0,
            "day_open": 2500.0,
            "prev_close": 2500.0,
        }

    def get_historical_candles(self, symbol: str, exchange: str, from_date: str, to_date: str, interval: str = "1d") -> List[Dict]:
        return self._mock_data.get("candles", [{"time": 1704067200, "open": 2500, "high": 2550, "low": 2480, "close": 2520, "volume": 1000000}])

    def get_all_instruments(self) -> List[Dict]:
        return self._mock_data.get("instruments", [{"trading_symbol": "RELIANCE", "exchange_token": "1234", "instrument_key": "NSE:RELIANCE"}])

    def place_order(self, **kwargs) -> Dict:
        return self._mock_data.get("order", {"success": True, "order_id": "MOCK_ORDER_123", "message": "Order placed successfully (mock)"})

    def get_order_status(self, segment: str, groww_order_id: str) -> Dict:
        return self._mock_data.get("order_status", {"status": "FILLED", "order_id": groww_order_id})


_groww_client_instance: Optional[GrowwClientBase] = None


def get_groww_client() -> GrowwClientBase:
    """Get the Groww client instance (singleton).

    This is the main entry point for getting a Groww client throughout the application.
    It returns a cached instance or creates a new one with proper authentication.
    """
    global _groww_client_instance

    if _groww_client_instance is None:
        _groww_client_instance = GrowwClient()
        logger.info("Created new GrowwClient instance")

    return _groww_client_instance


def set_groww_client(client: GrowwClientBase) -> None:
    """Set a custom Groww client (useful for testing)."""
    global _groww_client_instance
    _groww_client_instance = client
    logger.info("Custom GrowwClient set")


def reset_groww_client() -> None:
    """Reset the Groww client to create a new instance."""
    global _groww_client_instance
    _groww_client_instance = None
    logger.info("GrowwClient reset")


def fetch_ltp(symbols: List[str]) -> Dict[str, float]:
    """Fetch LTP for a list of symbols."""
    client = get_groww_client()
    exchange_syms = tuple(f"NSE_{s}" for s in symbols)
    ltp_data = client.get_ltp(exchange_syms)

    result = {}
    for key, val in ltp_data.items():
        sym = key.replace("NSE_", "")
        if isinstance(val, dict):
            result[sym] = float(val.get("ltp", 0))
        else:
            result[sym] = float(val) if val else 0.0

    return result


def fetch_quote(symbol: str) -> Dict:
    """Fetch quote for a symbol."""
    client = get_groww_client()
    return client.get_quote(symbol)


def fetch_candles(symbol: str, from_date: str, to_date: str, interval: str = "1d") -> List[Dict]:
    """Fetch historical candles for a symbol."""
    client = get_groww_client()
    return client.get_historical_candles(symbol=symbol, exchange="NSE", from_date=from_date, to_date=to_date, interval=interval)
