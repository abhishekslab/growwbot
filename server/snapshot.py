"""
Atomic JSON persistence for the last daily picks snapshot.

Survives server restarts — enables instant page load from the last scan result.
"""

import json
import os
import tempfile
import threading
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "daily_picks_snapshot.json")
_lock = threading.RLock()


def save_snapshot(data):
    # type: (Dict[str, Any]) -> None
    """Atomically write snapshot to disk using tempfile + os.replace."""
    payload = {
        "candidates": data.get("candidates", []),
        "meta": data.get("meta", {}),
        "saved_at": data.get("saved_at") or __import__("time").time(),
    }
    with _lock:
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(_SNAPSHOT_PATH), suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(payload, f)
            except Exception:
                os.close(fd)
                raise
            os.replace(tmp_path, _SNAPSHOT_PATH)
            logger.info("Snapshot saved: %d candidates", len(payload["candidates"]))
        except Exception as e:
            logger.error("Failed to save snapshot: %s", e)
            # Clean up temp file if it still exists
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def load_snapshot():
    # type: () -> Optional[Dict[str, Any]]
    """Read the last snapshot from disk. Returns None if missing or corrupt."""
    with _lock:
        if not os.path.exists(_SNAPSHOT_PATH):
            return None
        try:
            with open(_SNAPSHOT_PATH, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except Exception as e:
            logger.warning("Failed to load snapshot: %s", e)
            return None
