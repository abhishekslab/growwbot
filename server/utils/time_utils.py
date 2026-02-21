"""
Utility functions for Indian Standard Time (IST) handling.

IST is UTC+5:30. This module provides helper functions for market hours,
session boundaries, and time conversions.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

# IST offset from UTC: +5:30 hours
IST_OFFSET = timedelta(hours=5, minutes=30)

# Default trading session boundaries (IST)
DEFAULT_MARKET_OPEN_IST = "09:15"
DEFAULT_MARKET_CLOSE_IST = "15:30"
DEFAULT_TRADING_START_IST = "09:30"
DEFAULT_TRADING_END_IST = "15:00"
DEFAULT_FORCE_CLOSE_IST = "15:15"


def ist_now():
    # type: () -> datetime
    """Get current time in IST (Indian Standard Time)."""
    return datetime.now(timezone.utc) + IST_OFFSET


def utc_to_ist(utc_datetime):
    # type: (datetime) -> datetime
    """Convert UTC datetime to IST."""
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
    return utc_datetime + IST_OFFSET


def ist_to_utc(ist_datetime):
    # type: (datetime) -> datetime
    """Convert IST datetime to UTC."""
    if ist_datetime.tzinfo is None:
        ist_datetime = ist_datetime.replace(tzinfo=timezone.utc) + IST_OFFSET
    return ist_datetime - IST_OFFSET


def parse_ist_time(time_str):
    # type: (str) -> Tuple[int, int]
    """Parse IST time string (HH:MM) into (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def get_session_start_utc_hour_minute():
    # type: () -> Tuple[int, int]
    """
    Get the UTC hour and minute for market open (09:15 IST).
    Returns (3, 45) since 09:15 IST = 03:45 UTC.
    """
    # 09:15 IST = 03:45 UTC
    return 3, 45


def find_session_start_index(candles):
    # type: (list) -> int
    """
    Find the index of the session start in a list of candles.

    Session starts at 09:15 IST (03:45 UTC).
    Falls back to the first candle of the current day if exact boundary not found.

    Args:
        candles: List of candle dicts with "time" key (Unix timestamp)

    Returns:
        Index of session start candle
    """
    if not candles:
        return 0

    IST_START_UTC_H, IST_START_UTC_M = get_session_start_utc_hour_minute()

    # Search backwards for session start
    for i in range(len(candles) - 1, -1, -1):
        ts = candles[i]["time"]
        d = datetime.utcfromtimestamp(ts)
        utc_h = d.hour
        utc_m = d.minute

        # Check if this candle is at or very close to session start
        if utc_h == IST_START_UTC_H and IST_START_UTC_M <= utc_m < IST_START_UTC_M + 5:
            return i

        # Check for day boundary
        if i > 0:
            prev_d = datetime.utcfromtimestamp(candles[i - 1]["time"])
            if d.day != prev_d.day:
                return i

    return 0


def is_market_hours(
    start_time=DEFAULT_TRADING_START_IST,
    end_time=DEFAULT_TRADING_END_IST,
    ist_datetime=None,
):
    # type: (str, str, Optional[datetime]) -> bool
    """
    Check if given time is within market trading hours.

    Args:
        start_time: Trading start time in IST (HH:MM)
        end_time: Trading end time in IST (HH:MM)
        ist_datetime: Time to check (defaults to now)

    Returns:
        True if within trading hours
    """
    if ist_datetime is None:
        ist_datetime = ist_now()

    start_h, start_m = parse_ist_time(start_time)
    end_h, end_m = parse_ist_time(end_time)

    current_minutes = ist_datetime.hour * 60 + ist_datetime.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    return start_minutes <= current_minutes <= end_minutes


def get_market_status():
    # type: () -> dict
    """
    Get current market status information.

    Returns:
        Dict with market open status and time info
    """
    now = ist_now()

    market_open_h, market_open_m = parse_ist_time(DEFAULT_MARKET_OPEN_IST)
    market_close_h, market_close_m = parse_ist_time(DEFAULT_MARKET_CLOSE_IST)

    current_minutes = now.hour * 60 + now.minute
    market_open_minutes = market_open_h * 60 + market_open_m
    market_close_minutes = market_close_h * 60 + market_close_m

    is_open = market_open_minutes <= current_minutes <= market_close_minutes

    return {
        "is_open": is_open,
        "current_time_ist": now.strftime("%H:%M"),
        "market_open": DEFAULT_MARKET_OPEN_IST,
        "market_close": DEFAULT_MARKET_CLOSE_IST,
    }


def format_ist_datetime(dt):
    # type: (datetime) -> str
    """Format datetime in IST as string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = utc_to_ist(dt)
    return ist_dt.strftime("%Y-%m-%d %H:%M:%S IST")


def get_trading_window_config(
    trading_start=DEFAULT_TRADING_START_IST,
    trading_end=DEFAULT_TRADING_END_IST,
    force_close=DEFAULT_FORCE_CLOSE_IST,
):
    # type: (str, str, str) -> dict
    """
    Get trading window configuration for algorithms.

    Args:
        trading_start: Start of trading window (HH:MM IST)
        trading_end: End of trading window (HH:MM IST)
        force_close: Force close all positions (HH:MM IST)

    Returns:
        Configuration dict
    """
    return {
        "trading_start_ist": trading_start,
        "trading_end_ist": trading_end,
        "force_close_ist": force_close,
    }


def should_force_close(force_close_time=DEFAULT_FORCE_CLOSE_IST, ist_datetime=None):
    # type: (str, Optional[datetime]) -> bool
    """
    Check if we should force close all positions.

    Args:
        force_close_time: Force close time in IST (HH:MM)
        ist_datetime: Time to check (defaults to now)

    Returns:
        True if past force close time
    """
    if ist_datetime is None:
        ist_datetime = ist_now()

    fc_h, fc_m = parse_ist_time(force_close_time)
    current_minutes = ist_datetime.hour * 60 + ist_datetime.minute
    fc_minutes = fc_h * 60 + fc_m

    return current_minutes >= fc_minutes
