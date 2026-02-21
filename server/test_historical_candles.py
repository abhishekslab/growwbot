#!/usr/bin/env python3
"""
Test script for get_historical_candles (Backtesting API).
Prints full exception details on 403 or any error: status, headers, body.
Usage: cd server && python3 test_historical_candles.py
"""

import json
import os
import sys
from datetime import datetime, timedelta

# Run from server directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Load .env manually if present
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".groww_token")


def get_client():
    """Get GrowwAPI client from .groww_token or fresh auth."""
    from growwapi import GrowwAPI

    if os.path.isfile(TOKEN_FILE):
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
            token = data["token"]
            print("Using token from .groww_token")
            return GrowwAPI(token)
        except Exception as e:
            print("Could not load .groww_token: %s" % e)
    else:
        print(".groww_token not found at %s" % TOKEN_FILE)
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        print("Set API_KEY and API_SECRET in server/.env (or run get_token.py first)")
        sys.exit(1)
    print("Fetching new token...")
    token = GrowwAPI.get_access_token(api_key, secret=api_secret)
    return GrowwAPI(token)


def dump_exception(e):
    """Print everything useful about an exception (status, headers, body)."""
    print("\n--- Exception type: %s" % type(e).__name__)
    print("--- Exception message: %s" % e)

    # Common attributes on HTTP/client exceptions
    for attr in (
        "status_code",
        "response",
        "headers",
        "request",
        "code",
        "reason",
        "details",
    ):
        if hasattr(e, attr):
            val = getattr(e, attr)
            print("--- e.%s: %s" % (attr, val))
            if attr == "response" and val is not None:
                if hasattr(val, "status_code"):
                    print("    response.status_code: %s" % val.status_code)
                if hasattr(val, "headers"):
                    print("    response.headers: %s" % dict(val.headers))
                if hasattr(val, "text"):
                    print("    response.text: %s" % (val.text[:1000] if val.text else ""))
                if hasattr(val, "content"):
                    try:
                        print("    response.content (decode): %s" % (val.content[:1000].decode("utf-8", errors="replace") if val.content else ""))
                    except Exception:
                        print("    response.content: (raw bytes)")

    # Full __dict__ if present
    if hasattr(e, "__dict__") and e.__dict__:
        print("--- e.__dict__:")
        for k, v in e.__dict__.items():
            if k.startswith("_"):
                continue
            vstr = str(v)
            if len(vstr) > 500:
                vstr = vstr[:500] + "..."
            print("    %s: %s" % (k, vstr))

    # dir() to spot any other useful attrs
    all_attrs = [x for x in dir(e) if not x.startswith("_")]
    if all_attrs:
        print("--- Other attributes: %s" % ", ".join(all_attrs))
        for attr in all_attrs:
            if attr in ("status_code", "response", "headers", "request", "args", "code", "reason", "details"):
                continue
            try:
                val = getattr(e, attr)
                if callable(val):
                    continue
                print("    e.%s = %s" % (attr, val))
            except Exception:
                pass


def main():
    print("Loading Groww client...")
    groww = get_client()

    # Check if SDK exposes constants (your snippet uses them)
    print("\nChecking SDK constants...")
    for name in ("EXCHANGE_NSE", "SEGMENT_CASH", "CANDLE_INTERVAL_MIN_30"):
        if hasattr(groww, name):
            print("  groww.%s = %r" % (name, getattr(groww, name)))
        else:
            print("  groww.%s = (not found)" % name)

    # --- Test get_expiries (FNO) with latest year/month ---
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month
    print("\n--- get_expiries (NSE, NIFTY, year=%s, month=%s) ---" % (current_year, current_month))
    try:
        expiries_response = groww.get_expiries(
            exchange=getattr(groww, "EXCHANGE_NSE", "NSE"),
            underlying_symbol="NIFTY",
            year=current_year,
            month=current_month,
        )
        print("Success! Response: %s" % expiries_response)
        if isinstance(expiries_response, dict) and "expiries" in expiries_response:
            print("  expiries count: %d" % len(expiries_response["expiries"]))
    except Exception as e:
        print("*** ERROR ***")
        dump_exception(e)

    # Past 5 days, market hours only: 09:30–15:30 (IST)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=5)
    start_str = start_date.strftime("%Y-%m-%d") + " 09:30:00"
    end_str = end_date.strftime("%Y-%m-%d") + " 15:30:00"
    print("\nDate range: last 5 days, 09:30–15:30 only")
    print("  start_time = %s" % start_str)
    print("  end_time   = %s" % end_str)

    # Build kwargs: use constants if present, else strings
    kwargs = {
        "exchange": getattr(groww, "EXCHANGE_NSE", "NSE"),
        "segment": getattr(groww, "SEGMENT_CASH", "CASH"),
        "groww_symbol": "NSE-WIPRO",
        "start_time": start_str,
        "end_time": end_str,
        "candle_interval": getattr(groww, "CANDLE_INTERVAL_MIN_30", "30 min"),
    }
    print("\nCalling get_historical_candles with:")
    for k, v in kwargs.items():
        print("  %s = %r" % (k, v))

    try:
        historical_candles_response = groww.get_historical_candles(**kwargs)
        print("\nSuccess! Response type: %s" % type(historical_candles_response))
        if isinstance(historical_candles_response, dict):
            print("Keys: %s" % list(historical_candles_response.keys()))
            if "candles" in historical_candles_response:
                print("candles count: %d" % len(historical_candles_response["candles"]))
        elif isinstance(historical_candles_response, list):
            print("List length: %d" % len(historical_candles_response))
        else:
            print("Preview: %s" % str(historical_candles_response)[:500])
    except Exception as e:
        print("\n*** ERROR ***")
        dump_exception(e)
        sys.exit(1)


if __name__ == "__main__":
    print("test_historical_candles.py — Groww Backtesting API (get_historical_candles)")
    main()
