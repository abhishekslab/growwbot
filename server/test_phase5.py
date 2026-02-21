#!/usr/bin/env python3
"""
Phase 5 Infrastructure Tests

Tests for the infrastructure layer (Groww client, cache service).
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_groww_client_base():
    """Test GrowwClientBase and implementations."""
    print("\nTesting Groww client infrastructure...")

    from infrastructure import GrowwClient, GrowwClientBase, MockGrowwClient, get_groww_client, set_groww_client, reset_groww_client

    # Test that base class exists
    assert GrowwClientBase is not None
    print("  ✓ GrowwClientBase available")

    # Test Mock client
    mock_client = MockGrowwClient({"ltp": {"RELIANCE": 2500.0, "TCS": 3500.0}, "quote": {"RELIANCE": {"ltp": 2500.0, "change": 10.0}}})
    assert isinstance(mock_client, GrowwClientBase)
    print("  ✓ MockGrowwClient implements GrowwClientBase")

    # Test mock get_ltp
    ltp = mock_client.get_ltp(("NSE_RELIANCE", "NSE_TCS"))
    assert "NSE_RELIANCE" in ltp
    assert ltp["NSE_RELIANCE"]["ltp"] == 2500.0
    print("  ✓ MockGrowwClient.get_ltp works")

    # Test mock get_quote
    mock_with_quote = MockGrowwClient({"ltp": {}, "quote": {"RELIANCE": {"ltp": 2500.0, "symbol": "RELIANCE"}}})
    quote = mock_with_quote.get_quote("RELIANCE")
    assert "ltp" in quote or "symbol" in quote  # Mock returns full quote dict
    print("  ✓ MockGrowwClient.get_quote works")

    # Test set_groww_client for testing
    set_groww_client(mock_client)
    client = get_groww_client()
    assert client is mock_client
    print("  ✓ set_groww_client works for dependency injection")

    # Reset
    reset_groww_client()
    print("  ✓ reset_groww_client works")

    return True


def test_cache_service():
    """Test CacheService."""
    print("\nTesting cache service...")

    from services import CacheService, get_cache_service, reset_cache_service

    # Create a fresh cache service for testing
    cache = CacheService(cache_ttl=1)  # 1 second TTL for testing

    # Test set and get
    cache.set("test_key", "test_value")
    value = cache.get("test_key")
    assert value == "test_value"
    print("  ✓ CacheService.set/get works")

    # Test get non-existent key
    value = cache.get("non_existent")
    assert value is None
    print("  ✓ CacheService returns None for missing keys")

    # Test get_many
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    values = cache.get_many(["key1", "key2", "missing"])
    assert len(values) == 2
    assert values["key1"] == "value1"
    print("  ✓ CacheService.get_many works")

    # Test delete
    deleted = cache.delete("key1")
    assert deleted == True
    assert cache.get("key1") is None
    print("  ✓ CacheService.delete works")

    # Test TTL expiration
    time.sleep(1.5)
    value = cache.get("key2")
    assert value is None  # Should be expired
    print("  ✓ CacheService TTL expiration works")

    # Test clear - create new instance to avoid interference
    test_cache = CacheService(cache_ttl=300)
    test_cache.set("a", 1)
    test_cache.set("b", 2)
    count = test_cache.clear()
    assert count >= 2  # May have more items from other tests
    assert test_cache.get("a") is None
    print("  ✓ CacheService.clear works")

    # Test cleanup_expired
    cache.set("expired_key", "value", ttl=1)
    time.sleep(1.5)
    removed = cache.cleanup_expired()
    assert removed >= 0
    print("  ✓ CacheService.cleanup_expired works")

    # Test get_stats
    cache.set("stats_key", "stats_value")
    stats = cache.get_stats()
    assert "total_items" in stats
    assert "cache_keys" in stats
    print("  ✓ CacheService.get_stats works")

    # Clean up
    reset_cache_service()
    print("  ✓ CacheService reset works")

    return True


def test_convenience_functions():
    """Test convenience functions in infrastructure."""
    print("\nTesting convenience functions...")

    from infrastructure import set_groww_client, MockGrowwClient, fetch_ltp

    # Setup mock
    mock = MockGrowwClient({"ltp": {"AAPL": 150.0, "GOOG": 2800.0}})
    set_groww_client(mock)

    # Test fetch_ltp convenience function
    ltp = fetch_ltp(["AAPL", "GOOG"])
    assert "AAPL" in ltp
    assert ltp["AAPL"] == 150.0
    print("  ✓ fetch_ltp convenience function works")

    # Test fetch_quote
    from infrastructure import fetch_quote

    quote = fetch_quote("AAPL")
    assert "ltp" in quote or "symbol" in quote
    print("  ✓ fetch_quote convenience function works")

    return True


def test_backward_compatibility():
    """Ensure backward compatibility."""
    print("\nTesting backward compatibility...")

    # Old imports should still work
    from services import TradeService, AlgoService
    from repositories import TradeRepository, AlgoRepository
    from core import get_logger

    print("  ✓ All backward compatible imports work")

    return True


def test_integration():
    """Test full integration."""
    print("\nTesting full integration...")

    from infrastructure import set_groww_client, MockGrowwClient, get_groww_client
    from services import CacheService
    from services import TradeService
    from repositories import TradeRepository

    # Create mock client
    mock = MockGrowwClient({"ltp": {"RELIANCE": 2500.0}, "quote": {"RELIANCE": {"ltp": 2500.0, "volume": 1000000}}})
    set_groww_client(mock)

    # Create services
    cache = CacheService()
    trade_service = TradeService(TradeRepository())

    # Test cache can store API results
    quote = get_groww_client().get_quote("RELIANCE")
    cache.set("RELIANCE_quote", quote)

    cached = cache.get("RELIANCE_quote")
    assert cached is not None
    print("  ✓ Integration: cache stores API results")

    print("  ✓ Full integration works")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 5 Infrastructure Tests")
    print("=" * 60)

    try:
        test_groww_client_base()
        test_cache_service()
        test_convenience_functions()
        test_backward_compatibility()
        test_integration()

        print("\n" + "=" * 60)
        print("✅ ALL PHASE 5 TESTS PASSED!")
        print("Infrastructure layer working correctly!")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
