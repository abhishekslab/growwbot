"""
Authentication utilities for Groww API.

DB-backed token management with proactive background refresh.
Token is stored in the auth_tokens table (single-row, id=1).
A daemon thread refreshes the token ~10 min before expiry.
"""

import logging
import os
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_TOKEN_TTL = 28800  # 8 hours (matches actual Groww token validity)
_REFRESH_BEFORE = 600  # refresh 10 min before expiry
_REFRESH_CHECK_INTERVAL = 60  # daemon wakes every 60s
_AUTH_COOLDOWN = 60  # 1 minute cooldown after failed auth

# Old file-based token path (for one-time migration)
_OLD_TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
_OLD_TOKEN_FILE = os.path.join(_OLD_TOKEN_DIR, ".groww_token")

_cached_client = None  # type: Optional[object]
_cached_client_time = 0.0  # type: float
_auth_lock = threading.Lock()
_auth_fail_time = 0.0  # type: float

# Refresh daemon state
_refresh_thread = None  # type: Optional[threading.Thread]
_refresh_running = False
_migration_done = False


def _get_db_conn():
    """Get a DB connection using the shared trades_db infrastructure."""
    from trades_db import _get_conn
    return _get_conn()


def _load_token() -> Tuple[Optional[str], float]:
    """Load token from DB. Returns (token, created_at) or (None, 0).

    On first call, migrates any old file-based token to DB.
    """
    global _migration_done
    now = time.time()

    try:
        conn = _get_db_conn()
        row = conn.execute(
            "SELECT access_token, created_at, expires_at FROM auth_tokens WHERE id = 1"
        ).fetchone()
        conn.close()

        if row:
            token, created_at, expires_at = row[0], row[1], row[2]
            if expires_at > now:
                return token, created_at
            else:
                logger.info("DB token expired (%.0fs ago)", now - expires_at)
                return None, 0
    except Exception as e:
        logger.warning("Failed to load token from DB: %s", e)

    # One-time migration from old file-based token
    if not _migration_done:
        _migration_done = True
        _migrate_file_token()
        # Retry after migration
        try:
            conn = _get_db_conn()
            row = conn.execute(
                "SELECT access_token, created_at, expires_at FROM auth_tokens WHERE id = 1"
            ).fetchone()
            conn.close()
            if row and row[2] > now:
                return row[0], row[1]
        except Exception:
            pass

    return None, 0


def _save_token(token):
    # type: (str) -> None
    """Persist token to DB (upsert single row)."""
    now = time.time()
    expires_at = now + _TOKEN_TTL
    try:
        conn = _get_db_conn()
        conn.execute(
            "INSERT OR REPLACE INTO auth_tokens (id, access_token, created_at, expires_at, updated_at) "
            "VALUES (1, ?, ?, ?, ?)",
            (token, now, expires_at, now),
        )
        conn.commit()
        conn.close()
        logger.info("Token saved to DB (expires in %.0fs)", _TOKEN_TTL)
    except Exception as e:
        logger.warning("Failed to save token to DB: %s", e)


def _migrate_file_token():
    """One-time migration: move old file-based token to DB, then delete the file."""
    try:
        if not os.path.exists(_OLD_TOKEN_FILE):
            return

        with open(_OLD_TOKEN_FILE) as f:
            token = f.read().strip()

        if not token:
            return

        # If it's a JSON blob (from get_token.py format), extract the token
        if token.startswith("{"):
            import json
            data = json.loads(token)
            token = data.get("token", token)

        file_age = time.time() - os.path.getmtime(_OLD_TOKEN_FILE)
        if file_age > _TOKEN_TTL:
            logger.info("Old file token too old (%.0fs), skipping migration", file_age)
            return

        _save_token(token)
        logger.info("Migrated token from file to DB")

        # Remove old file
        try:
            os.remove(_OLD_TOKEN_FILE)
            logger.info("Deleted old token file: %s", _OLD_TOKEN_FILE)
        except Exception as e:
            logger.warning("Could not delete old token file: %s", e)

    except Exception as e:
        logger.warning("File-to-DB token migration failed: %s", e)


def _do_fresh_auth():
    """Authenticate with Groww API and save the new token.

    On success: saves to DB, updates in-memory cached client.
    On failure: sets _auth_fail_time, logs warning.
    """
    global _auth_fail_time

    now = time.time()
    if _auth_fail_time and (now - _auth_fail_time) < _AUTH_COOLDOWN:
        wait = int(_AUTH_COOLDOWN - (now - _auth_fail_time))
        logger.warning("Auth rate-limited. Retry in %ds", wait)
        return None

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        logger.warning("API_KEY and API_SECRET not set — cannot authenticate")
        return None

    with _auth_lock:
        # Double-check after acquiring lock — another thread may have refreshed
        existing_token, _ = _load_token()
        if existing_token:
            logger.info("Token already refreshed by another thread")
            from growwapi import GrowwAPI
            client = GrowwAPI(existing_token)
            set_cached_client(client)
            return client

        try:
            from growwapi import GrowwAPI
            access_token = GrowwAPI.get_access_token(api_key, secret=api_secret)
            _save_token(access_token)
            client = GrowwAPI(access_token)
            set_cached_client(client)
            _auth_fail_time = 0
            logger.info("Fresh auth successful, token saved to DB")
            return client
        except Exception as e:
            logger.warning("Auth failed: %s", e)
            _auth_fail_time = time.time()
            return None


def _token_refresh_loop():
    """Background loop that proactively refreshes the token before expiry."""
    global _refresh_running
    logger.info("Token refresh daemon started")

    while _refresh_running:
        try:
            time.sleep(_REFRESH_CHECK_INTERVAL)
            if not _refresh_running:
                break

            now = time.time()

            # Check current token state from DB
            try:
                conn = _get_db_conn()
                row = conn.execute(
                    "SELECT expires_at FROM auth_tokens WHERE id = 1"
                ).fetchone()
                conn.close()
            except Exception as e:
                logger.warning("Refresh daemon DB read failed: %s", e)
                continue

            if not row:
                # No token at all — try to get one
                logger.info("No token in DB, attempting fresh auth")
                _do_fresh_auth()
                continue

            expires_at = row[0]
            remaining = expires_at - now

            if remaining < _REFRESH_BEFORE:
                logger.info(
                    "Token expires in %.0fs (< %ds threshold), refreshing proactively",
                    remaining, _REFRESH_BEFORE,
                )
                _do_fresh_auth()
            # else: token is still valid, no action needed

        except Exception as e:
            logger.warning("Refresh daemon error: %s", e)

    logger.info("Token refresh daemon stopped")


def start_token_refresh_daemon():
    """Start the background token refresh daemon thread."""
    global _refresh_thread, _refresh_running

    if _refresh_thread and _refresh_thread.is_alive():
        logger.warning("Token refresh daemon already running")
        return

    _refresh_running = True
    _refresh_thread = threading.Thread(
        target=_token_refresh_loop, name="token-refresh", daemon=True
    )
    _refresh_thread.start()


def stop_token_refresh_daemon():
    """Stop the background token refresh daemon thread."""
    global _refresh_running, _refresh_thread

    if not _refresh_thread:
        return

    _refresh_running = False
    _refresh_thread.join(timeout=_REFRESH_CHECK_INTERVAL + 5)
    _refresh_thread = None
    logger.info("Token refresh daemon join complete")


# --- In-memory client cache (unchanged interface) ---

def get_cached_client():
    # type: () -> Optional[object]
    """Get the cached client if still valid."""
    global _cached_client, _cached_client_time
    now = time.time()
    if _cached_client and (now - _cached_client_time) < _TOKEN_TTL:
        return _cached_client
    return None


def set_cached_client(client):
    # type: (object) -> None
    """Set the cached client."""
    global _cached_client, _cached_client_time
    _cached_client = client
    _cached_client_time = time.time()


def get_auth_fail_time():
    # type: () -> float
    """Get the auth fail timestamp."""
    global _auth_fail_time
    return _auth_fail_time


def set_auth_fail_time(timestamp):
    # type: (float) -> None
    """Set the auth fail timestamp."""
    global _auth_fail_time
    _auth_fail_time = timestamp


def get_auth_lock():
    # type: () -> threading.Lock
    """Get the auth lock."""
    return _auth_lock


def get_token_ttl():
    # type: () -> int
    """Get token TTL."""
    return _TOKEN_TTL


def get_auth_cooldown():
    # type: () -> int
    """Get auth cooldown."""
    return _AUTH_COOLDOWN
