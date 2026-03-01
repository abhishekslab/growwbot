"""
Global rate limiter for Groww API calls.

Groww enforces rate limits at the type level:
- Orders (place_order): 10/s, 250/min
- Live Data (get_ltp, get_ohlc, get_quote, get_historical_candles): 10/s, 300/min
- Non Trading (get_order_status, get_holdings_for_user, get_all_instruments): 20/s, 500/min

Uses a sliding window log algorithm — stores timestamps of recent requests in a deque,
counts entries in 1s and 60s windows to enforce both limits simultaneously.
"""

import threading
import time
from collections import deque

from core.logging_config import get_logger

logger = get_logger("rate_limiter")


class RateBucket:
    """Single rate-limit bucket with per-second and per-minute limits."""

    def __init__(self, name, per_second, per_minute):
        # type: (str, int, int) -> None
        self.name = name
        self.per_second = per_second
        self.per_minute = per_minute
        self._timestamps = deque()  # type: deque
        self._lock = threading.Lock()

    def acquire(self, timeout=30.0):
        # type: (float) -> bool
        """Block until a slot is available. Returns False on timeout."""
        deadline = time.monotonic() + timeout

        while True:
            sleep_time = self._try_acquire()
            if sleep_time == 0:
                return True

            if time.monotonic() + sleep_time > deadline:
                logger.warning(
                    "Rate limit timeout: bucket=%s, waited=%.1fs",
                    self.name, timeout,
                )
                return False

            logger.debug(
                "Rate limited: bucket=%s, sleeping=%.2fs",
                self.name, sleep_time,
            )
            # Sleep outside the lock so other threads aren't blocked
            time.sleep(sleep_time)

    def _try_acquire(self):
        # type: () -> float
        """Try to acquire a slot. Returns 0 if acquired, or seconds to wait."""
        now = time.monotonic()

        with self._lock:
            # Prune entries older than 60s
            cutoff_60s = now - 60.0
            while self._timestamps and self._timestamps[0] < cutoff_60s:
                self._timestamps.popleft()

            # Count requests in last 1s
            cutoff_1s = now - 1.0
            count_1s = 0
            for ts in reversed(self._timestamps):
                if ts >= cutoff_1s:
                    count_1s += 1
                else:
                    break

            count_60s = len(self._timestamps)

            # Check per-second limit
            if count_1s >= self.per_second:
                # Wait until the oldest 1s-window entry expires
                oldest_1s = None
                for ts in self._timestamps:
                    if ts >= cutoff_1s:
                        oldest_1s = ts
                        break
                if oldest_1s is not None:
                    return (oldest_1s + 1.0) - now + 0.01
                return 0.1

            # Check per-minute limit
            if count_60s >= self.per_minute:
                oldest = self._timestamps[0]
                return (oldest + 60.0) - now + 0.01

            # Slot available — record and proceed
            self._timestamps.append(now)
            return 0

    def status(self):
        # type: () -> Dict
        """Return current usage stats for this bucket."""
        now = time.monotonic()
        with self._lock:
            cutoff_60s = now - 60.0
            cutoff_1s = now - 1.0

            count_60s = sum(1 for ts in self._timestamps if ts >= cutoff_60s)
            count_1s = sum(1 for ts in self._timestamps if ts >= cutoff_1s)

        return {
            "name": self.name,
            "per_second": {"used": count_1s, "limit": self.per_second},
            "per_minute": {"used": count_60s, "limit": self.per_minute},
        }


class GrowwRateLimiter:
    """Holds rate-limit buckets for each Groww API type."""

    ORDERS = "orders"
    LIVE_DATA = "live_data"
    NON_TRADING = "non_trading"

    def __init__(self):
        self._buckets = {
            self.ORDERS: RateBucket("orders", per_second=10, per_minute=250),
            self.LIVE_DATA: RateBucket("live_data", per_second=10, per_minute=300),
            self.NON_TRADING: RateBucket("non_trading", per_second=20, per_minute=500),
        }

    def acquire(self, bucket_type, timeout=30.0):
        # type: (str, float) -> bool
        """Acquire a slot in the given bucket. Returns False on timeout."""
        bucket = self._buckets.get(bucket_type)
        if bucket is None:
            logger.warning("Unknown rate limit bucket: %s", bucket_type)
            return True
        return bucket.acquire(timeout)

    def status(self):
        # type: () -> Dict
        """Return usage stats for all buckets."""
        return {name: bucket.status() for name, bucket in self._buckets.items()}


_instance = None  # type: Optional[GrowwRateLimiter]
_instance_lock = threading.Lock()


def get_rate_limiter():
    # type: () -> GrowwRateLimiter
    """Thread-safe singleton accessor for the global rate limiter."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = GrowwRateLimiter()
                logger.info("Global rate limiter initialized")
    return _instance
