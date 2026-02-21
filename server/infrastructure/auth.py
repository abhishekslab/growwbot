"""
Authentication utilities for Groww API.

This module handles token management, caching, and persistence independently
of the FastAPI app to avoid circular imports.
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_TOKEN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
_TOKEN_FILE = os.path.join(_TOKEN_DIR, ".groww_token")
_TOKEN_TTL = 3600  # 1 hour
_AUTH_COOLDOWN = 60  # 1 minute

_cached_client: Optional[object] = None
_cached_client_time: float = 0
_auth_lock = threading.Lock()
_auth_fail_time: float = 0


def _ensure_token_dir() -> None:
    """Ensure the token directory exists."""
    Path(_TOKEN_DIR).mkdir(parents=True, exist_ok=True)


def _load_token() -> Tuple[Optional[str], float]:
    """Load persisted token from disk. Returns (token, timestamp) or (None, 0)."""
    _ensure_token_dir()
    try:
        if os.path.exists(_TOKEN_FILE):
            mtime = os.path.getmtime(_TOKEN_FILE)
            with open(_TOKEN_FILE) as f:
                return f.read().strip(), mtime
    except Exception as e:
        logger.warning("Failed to load token: %s", e)
    return None, 0


def _save_token(token: str) -> None:
    """Persist token to disk."""
    _ensure_token_dir()
    try:
        with open(_TOKEN_FILE, "w") as f:
            f.write(token)
    except Exception as e:
        logger.warning("Failed to save token: %s", e)


def get_cached_client() -> Optional[object]:
    """Get the cached client if still valid."""
    global _cached_client, _cached_client_time
    now = time.time()
    if _cached_client and (now - _cached_client_time) < _TOKEN_TTL:
        return _cached_client
    return None


def set_cached_client(client: object) -> None:
    """Set the cached client."""
    global _cached_client, _cached_client_time
    _cached_client = client
    _cached_client_time = time.time()


def get_auth_fail_time() -> float:
    """Get the auth fail timestamp."""
    global _auth_fail_time
    return _auth_fail_time


def set_auth_fail_time(timestamp: float) -> None:
    """Set the auth fail timestamp."""
    global _auth_fail_time
    _auth_fail_time = timestamp


def get_auth_lock() -> threading.Lock:
    """Get the auth lock."""
    return _auth_lock


def get_token_ttl() -> int:
    """Get token TTL."""
    return _TOKEN_TTL


def get_auth_cooldown() -> int:
    """Get auth cooldown."""
    return _AUTH_COOLDOWN
