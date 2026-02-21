"""
System and health check API routes.

Provides health monitoring, metrics, and system information endpoints.
"""

import os
import platform
import time
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core import get_logger

router = APIRouter(prefix="/api/system", tags=["system"])
logger = get_logger("api.system")

# Track server start time
START_TIME = time.time()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        uptime_seconds = int(time.time() - START_TIME)
        uptime_str = format_uptime(uptime_seconds)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime": uptime_str,
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()})


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes/docker-compose."""
    try:
        # Check database connectivity
        from trades_db import _get_conn

        conn = _get_conn()
        conn.execute("SELECT 1")
        conn.close()

        return {"status": "ready", "checks": {"database": "ok"}, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "checks": {"database": f"error: {str(e)}"}, "timestamp": datetime.utcnow().isoformat()}
        )


@router.get("/metrics")
async def get_metrics():
    """Get application metrics."""
    try:
        from trades_db import list_trades, get_summary

        # Get trade counts
        open_trades = list_trades(status="OPEN")
        total_trades = list_trades()
        summary = get_summary()

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "trades": {
                "total": len(total_trades),
                "open": len(open_trades),
                "closed": len(total_trades) - len(open_trades),
                "win_rate": summary.get("win_rate", 0),
                "total_pnl": summary.get("total_pnl", 0),
            },
            "system": {"uptime_seconds": int(time.time() - START_TIME), "python_version": platform.python_version(), "platform": platform.platform()},
        }

        return metrics
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to collect metrics", "message": str(e)})


@router.get("/info")
async def get_system_info():
    """Get system information."""
    return {
        "application": "GrowwBot API",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "python": {"version": platform.python_version(), "implementation": platform.python_implementation()},
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/logs")
async def get_recent_logs(lines: int = 50):
    """Get recent log entries (last N lines)."""
    try:
        log_file = "logs/growwbot.log"
        if not os.path.exists(log_file):
            return {"success": True, "logs": [], "message": "Log file not found"}

        # Read last N lines
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {"success": True, "lines": len(recent_lines), "logs": [line.strip() for line in recent_lines]}
    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


def format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)
