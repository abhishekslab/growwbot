#!/usr/bin/env python3
"""
One-time token bootstrap script.

Usage:
    python3 get_token.py

Reads API_KEY and API_SECRET from .env, obtains an access token from the
Groww auth endpoint, and saves it to .groww_token for the server to pick up.

If the auth endpoint is rate-limited, the script waits and retries.
"""

import os
import sys
import json
import time

from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".groww_token")

RETRY_INTERVAL = 60  # seconds between retries on rate limit
MAX_RETRIES = 30     # give up after ~30 minutes


def save_token_file(token):
    """Save token to .groww_token (same format as main.py _save_token)."""
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TOKEN_FILE) or ".")
    with os.fdopen(fd, "w") as f:
        json.dump({"token": token, "time": time.time()}, f)
    os.replace(tmp, TOKEN_FILE)


def main():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    if not api_key or not api_secret:
        print("ERROR: API_KEY and API_SECRET must be set in server/.env")
        sys.exit(1)

    print("Attempting to obtain Groww access token...")
    print("API_KEY: %s...%s" % (api_key[:4], api_key[-4:]))

    from growwapi import GrowwAPI

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            token = GrowwAPI.get_access_token(api_key, secret=api_secret)
            print("\nToken obtained successfully!")

            save_token_file(token)
            print("Saved to %s" % TOKEN_FILE)

            print("\nYou can now start the server:")
            print("  python3 -m uvicorn main:app --reload")
            print("Token is valid for ~8 hours.")
            return

        except Exception as e:
            err_str = str(e).lower()
            if "rate" in err_str or "limit" in err_str or "429" in err_str or "too many" in err_str:
                print("[Attempt %d/%d] Rate limited: %s" % (attempt, MAX_RETRIES, e))
                print("  Retrying in %ds..." % RETRY_INTERVAL)
                time.sleep(RETRY_INTERVAL)
            else:
                print("ERROR: Authentication failed: %s" % e)
                sys.exit(1)

    print("ERROR: Gave up after %d attempts. Try again later." % MAX_RETRIES)
    sys.exit(1)


if __name__ == "__main__":
    main()
