"""
Unit tests for services module.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.holdings_service import HoldingsService, HoldingsError
from services.cache_service import CacheService
from services.algo_service import AlgoService
from repositories.algo_repository import AlgoRepository


class TestHoldingsService:
    def test_holdings_service_creation(self, mock_groww_client):
        service = HoldingsService(mock_groww_client)
        assert service._groww == mock_groww_client

    def test_holdings_get_holdings(self, mock_groww_client):
        service = HoldingsService(mock_groww_client)
        result = service.get_holdings()

        assert "holdings" in result
        assert "summary" in result
        assert len(result["holdings"]) == 2

    def test_holdings_fetch_ltp_batch(self, mock_groww_client):
        service = HoldingsService(mock_groww_client)
        symbols = ["NSE_RELIANCE", "NSE_TCS"]
        ltp_map = service._fetch_ltp_batch(symbols)

        assert "NSE_RELIANCE" in ltp_map
        assert "NSE_TCS" in ltp_map
        assert ltp_map["NSE_RELIANCE"] == 2500.0


class TestCacheService:
    def test_cache_service_creation(self):
        cache = CacheService(cache_ttl=60)
        assert cache._default_ttl == 60

    def test_cache_set_get(self):
        cache = CacheService(cache_ttl=60)
        cache.set("key1", {"data": "value"})
        result = cache.get("key1")
        assert result == {"data": "value"}

    def test_cache_get_missing(self):
        cache = CacheService(cache_ttl=60)
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_delete(self):
        cache = CacheService(cache_ttl=60)
        cache.set("key1", "value")
        cache.delete("key1")
        result = cache.get("key1")
        assert result is None

    def test_cache_get_many(self):
        cache = CacheService(cache_ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        result = cache.get_many(["key1", "key2"])
        assert "key1" in result
        assert "key2" in result
        assert result["key1"] == "value1"

    def test_cache_clear(self):
        cache = CacheService(cache_ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestAlgoService:
    def test_algo_service_creation(self):
        repo = AlgoRepository()
        service = AlgoService(repo)
        assert service.repository is not None
