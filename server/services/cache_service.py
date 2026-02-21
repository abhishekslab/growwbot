"""
Cache service for market data caching.

Wraps the existing MarketCache with a service interface for better testability.
"""

import threading
import time
from typing import Any, Dict, List, Optional

from core.logging_config import get_logger

logger = get_logger("services.cache")


class CacheService:
    """Service for caching market data."""

    def __init__(self, cache_ttl: int = 300):
        """
        Initialize cache service.

        Args:
            cache_ttl: Default TTL in seconds for cached data
        """
        self._cache: Dict[str, Any] = {}
        self._cache_times: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._default_ttl = cache_ttl
        logger.info(f"CacheService initialized with TTL={cache_ttl}s")

    def get(self, key: str, ttl: int = None) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            key: Cache key
            ttl: Optional TTL override (uses default if not specified)

        Returns:
            Cached value or None if not found/expired
        """
        ttl = ttl or self._default_ttl

        with self._lock:
            if key not in self._cache:
                return None

            # Check expiration
            if time.time() - self._cache_times.get(key, 0) > ttl:
                del self._cache[key]
                del self._cache_times[key]
                return None

            return self._cache[key]

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        ttl = ttl or self._default_ttl

        with self._lock:
            self._cache[key] = value
            self._cache_times[key] = time.time()
            logger.debug(f"Cache set: {key}")

    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._cache_times[key]
                logger.debug(f"Cache deleted: {key}")
                return True
            return False

    def clear(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of items cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._cache_times.clear()
            logger.info(f"Cache cleared: {count} items")
            return count

    def get_many(self, keys: List[str], ttl: int = None) -> Dict[str, Any]:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys
            ttl: Optional TTL override

        Returns:
            Dict of found key-value pairs
        """
        result = {}
        for key in keys:
            value = self.get(key, ttl)
            if value is not None:
                result[key] = value
        return result

    def set_many(self, items: Dict[str, Any], ttl: int = None) -> None:
        """
        Set multiple values in cache.

        Args:
            items: Dict of key-value pairs to cache
            ttl: Optional TTL override
        """
        for key, value in items.items():
            self.set(key, value, ttl)
        logger.debug(f"Cache set_many: {len(items)} items")

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of expired items removed
        """
        removed = 0
        current_time = time.time()

        with self._lock:
            expired_keys = [key for key, cached_time in self._cache_times.items() if current_time - cached_time > self._default_ttl]

            for key in expired_keys:
                del self._cache[key]
                del self._cache_times[key]
                removed += 1

        if removed > 0:
            logger.info(f"Cache cleanup: removed {removed} expired items")

        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {"total_items": len(self._cache), "cache_keys": list(self._cache.keys()), "default_ttl": self._default_ttl}


# Singleton instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get the singleton CacheService instance."""
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()

    return _cache_service


def reset_cache_service() -> None:
    """Reset the cache service."""
    global _cache_service
    if _cache_service:
        _cache_service.clear()
    _cache_service = None
    logger.info("CacheService reset")
