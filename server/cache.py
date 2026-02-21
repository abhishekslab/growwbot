"""
In-memory cache for market data with TTL-based expiration.

Speeds up screener re-runs from ~30s to near-instant on warm cache.
"""

import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# TTLs in seconds
TTL_INSTRUMENTS = 24 * 3600  # 24 hours
TTL_OHLC = 5 * 60  # 5 minutes
TTL_HISTORICAL = 24 * 3600  # 24 hours
TTL_NEWS = 6 * 3600  # 6 hours


class _CacheEntry:
    __slots__ = ("data", "expires_at")

    def __init__(self, data, ttl):
        self.data = data
        self.expires_at = time.monotonic() + ttl

    @property
    def alive(self):
        return time.monotonic() < self.expires_at


class MarketCache:
    def __init__(self):
        self._lock = threading.RLock()
        self._instruments = None  # _CacheEntry | None
        self._ohlc = {}  # frozenset(symbols) -> _CacheEntry
        self._historical = {}  # symbol -> _CacheEntry
        self._news = {}  # company_name -> _CacheEntry
        self._warming = False
        self._last_warmup = None  # datetime | None
        self._ltp = {}  # str -> float ("NSE_SYMBOL" -> price)
        self._ltp_updated_at = 0.0  # time.monotonic()

    # ------------------------------------------------------------------
    # Instruments
    # ------------------------------------------------------------------
    def get_instruments(self, groww):
        with self._lock:
            if self._instruments and self._instruments.alive:
                return self._instruments.data

        # Fetch outside lock to avoid blocking
        df = groww.get_all_instruments()

        with self._lock:
            self._instruments = _CacheEntry(df, TTL_INSTRUMENTS)
        return df

    # ------------------------------------------------------------------
    # OHLC batch
    # ------------------------------------------------------------------
    def get_ohlc_batch(self, groww, symbols_tuple):
        key = frozenset(symbols_tuple)
        with self._lock:
            entry = self._ohlc.get(key)
            if entry and entry.alive:
                return entry.data

        # Fetch outside lock
        ohlc = groww.get_ohlc(exchange_trading_symbols=symbols_tuple, segment="CASH")

        with self._lock:
            self._ohlc[key] = _CacheEntry(ohlc, TTL_OHLC)
        return ohlc

    # ------------------------------------------------------------------
    # Historical candles
    # ------------------------------------------------------------------
    def get_historical_candles(self, groww, symbol, start_str, end_str):
        with self._lock:
            entry = self._historical.get(symbol)
            if entry and entry.alive:
                return entry.data

        candles = groww.get_historical_candles("NSE", "CASH", symbol, start_str, end_str, "1day")

        with self._lock:
            self._historical[symbol] = _CacheEntry(candles, TTL_HISTORICAL)
        return candles

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------
    def get_news(self, name, fetch_fn):
        """Cache news results. fetch_fn(name) -> result."""
        with self._lock:
            entry = self._news.get(name)
            if entry and entry.alive:
                return entry.data

        result = fetch_fn(name)

        with self._lock:
            self._news[name] = _CacheEntry(result, TTL_NEWS)
        return result

    # ------------------------------------------------------------------
    # Warmup
    # ------------------------------------------------------------------
    def warmup(self, groww):
        """Pre-fetch instruments and OHLC batches in the background."""
        with self._lock:
            if self._warming:
                return
            self._warming = True

        try:
            logger.info("Cache warmup started")
            df = self.get_instruments(groww)

            # Filter to NSE CASH
            if "exchange" in df.columns and "segment" in df.columns:
                mask = (df["exchange"] == "NSE") & (df["segment"] == "CASH")
                df = df[mask]
            elif "exchange" in df.columns:
                df = df[df["exchange"] == "NSE"]

            symbols = df["trading_symbol"].tolist()
            # API requires NSE_SYMBOL format for exchange_trading_symbols
            exchange_symbols = [f"NSE_{s}" for s in symbols]
            batch_size = 50
            for i in range(0, len(exchange_symbols), batch_size):
                batch = tuple(exchange_symbols[i : i + batch_size])
                try:
                    self.get_ohlc_batch(groww, batch)
                except Exception as e:
                    logger.warning("Warmup OHLC batch %d failed: %s", i, e)
                time.sleep(0.1)

            with self._lock:
                self._last_warmup = datetime.now()
            logger.info("Cache warmup complete")
        finally:
            with self._lock:
                self._warming = False

    # ------------------------------------------------------------------
    # LTP store
    # ------------------------------------------------------------------
    def update_ltp_batch(self, ltp_map):
        """Merge batch LTP values into the store and update timestamp."""
        with self._lock:
            self._ltp.update(ltp_map)
            self._ltp_updated_at = time.monotonic()

    def get_ltp_map(self):
        """Return a copy of the current LTP store."""
        with self._lock:
            return dict(self._ltp)

    def ltp_age_seconds(self):
        """Seconds since last LTP update, or float('inf') if never updated."""
        with self._lock:
            if self._ltp_updated_at == 0.0:
                return float("inf")
            return time.monotonic() - self._ltp_updated_at

    # ------------------------------------------------------------------
    # Status / clear
    # ------------------------------------------------------------------
    def status(self):
        with self._lock:
            return {
                "instruments_cached": bool(self._instruments and self._instruments.alive),
                "ohlc_batches": sum(1 for e in self._ohlc.values() if e.alive),
                "historical_symbols": sum(1 for e in self._historical.values() if e.alive),
                "news_entries": sum(1 for e in self._news.values() if e.alive),
                "warming": self._warming,
                "last_warmup": (self._last_warmup.isoformat() if self._last_warmup else None),
                "ltp_symbols": len(self._ltp),
                "ltp_age_seconds": round(time.monotonic() - self._ltp_updated_at, 1) if self._ltp_updated_at > 0 else None,
            }

    def clear(self):
        with self._lock:
            self._instruments = None
            self._ohlc.clear()
            self._historical.clear()
            self._news.clear()
            self._last_warmup = None
            self._ltp.clear()
            self._ltp_updated_at = 0.0


# Module-level singleton instance for easy importing
market_cache = MarketCache()
