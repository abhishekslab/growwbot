"""
Algorithm API routes with comprehensive logging.

Provides endpoints for algorithm management and monitoring.
"""

import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import get_logger, log_error
from core.exceptions import AlgorithmError, ValidationError
from services.algo_service import AlgoService
from app.dependencies import get_algo_service

router = APIRouter(prefix="/api/algos", tags=["algorithms"])
logger = get_logger("api.algos")


@router.get("/")
async def list_algos(service: AlgoService = Depends(get_algo_service)):
    """List all algorithms with their status."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Listing algorithms")

        settings = service.get_all_settings()

        # Convert to list of algo info
        algos = []
        for algo_id, config in settings.items():
            if hasattr(config, "dict"):
                algos.append(
                    {"id": algo_id, "enabled": config.enabled, "config": config.config.dict() if hasattr(config.config, "dict") else config.config}
                )
            else:
                algos.append({"id": algo_id, "enabled": config.get("enabled", False), "config": config.get("config", {})})

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Found {len(algos)} algorithms in {duration:.2f}ms")

        return {"success": True, "count": len(algos), "algos": algos}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "list_algos"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{algo_id}")
async def get_algo(algo_id: str, service: AlgoService = Depends(get_algo_service)):
    """Get algorithm details."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting algo {algo_id}")

        settings = service.get_settings(algo_id)
        if not settings:
            logger.warning(f"[{request_id}] Algorithm {algo_id} not found")
            raise HTTPException(status_code=404, detail=f"Algorithm {algo_id} not found")

        logger.info(f"[{request_id}] Algorithm {algo_id} found")

        return {"success": True, "algo_id": algo_id, "settings": settings.dict() if hasattr(settings, "dict") else settings}
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "algo_id": algo_id, "endpoint": "get_algo"})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{algo_id}/start")
async def start_algo(algo_id: str, service: AlgoService = Depends(get_algo_service)):
    """Enable/start an algorithm."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Starting algorithm {algo_id}")

        settings = service.enable_algo(algo_id)

        logger.info(f"[{request_id}] Algorithm {algo_id} started")

        return {
            "success": True,
            "algo_id": algo_id,
            "enabled": settings.enabled if hasattr(settings, "enabled") else settings.get("enabled"),
            "message": f"Algorithm {algo_id} started",
        }
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "algo_id": algo_id, "endpoint": "start_algo"})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{algo_id}/stop")
async def stop_algo(algo_id: str, service: AlgoService = Depends(get_algo_service)):
    """Disable/stop an algorithm."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Stopping algorithm {algo_id}")

        settings = service.disable_algo(algo_id)

        logger.info(f"[{request_id}] Algorithm {algo_id} stopped")

        return {
            "success": True,
            "algo_id": algo_id,
            "enabled": settings.enabled if hasattr(settings, "enabled") else settings.get("enabled"),
            "message": f"Algorithm {algo_id} stopped",
        }
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "algo_id": algo_id, "endpoint": "stop_algo"})
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{algo_id}/settings")
async def update_algo_settings(algo_id: str, settings_data: dict, service: AlgoService = Depends(get_algo_service)):
    """Update algorithm settings."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Updating settings for algorithm {algo_id}")

        # Create settings object
        try:
            from domain.models import AlgoSettings

            settings = AlgoSettings(**settings_data)
        except ImportError:
            settings = settings_data

        updated = service.update_settings(algo_id, settings)

        logger.info(f"[{request_id}] Settings updated for algorithm {algo_id}")

        return {"success": True, "algo_id": algo_id, "settings": updated.dict() if hasattr(updated, "dict") else updated}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "algo_id": algo_id, "endpoint": "update_algo_settings"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{algo_id}/signals")
async def get_algo_signals(
    algo_id: str,
    limit: int = Query(50, ge=1, le=200, description="Number of signals to return"),
    exclude_skips: bool = Query(True, description="Exclude SKIP signals"),
    service: AlgoService = Depends(get_algo_service),
):
    """Get algorithm signals/decisions."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Getting signals for algorithm {algo_id} (limit={limit})")

        signals = service.get_signals(algo_id=algo_id, limit=limit, exclude_skips=exclude_skips)

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Found {len(signals)} signals in {duration:.2f}ms")

        return {"success": True, "algo_id": algo_id, "count": len(signals), "signals": [s.dict() if hasattr(s, "dict") else s for s in signals]}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "algo_id": algo_id, "endpoint": "get_algo_signals"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{algo_id}/performance")
async def get_algo_performance(
    algo_id: str, is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: AlgoService = Depends(get_algo_service)
):
    """Get algorithm performance metrics."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting performance for algorithm {algo_id}")

        deployed_capital = service.get_deployed_capital(algo_id, is_paper if is_paper is not None else True)
        net_pnl = service.get_net_pnl(algo_id, is_paper if is_paper is not None else True)

        logger.info(f"[{request_id}] Performance: deployed={deployed_capital}, pnl={net_pnl}")

        return {"success": True, "algo_id": algo_id, "is_paper": is_paper, "deployed_capital": deployed_capital, "net_pnl": net_pnl}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "algo_id": algo_id, "endpoint": "get_algo_performance"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance(
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: AlgoService = Depends(get_algo_service)
):
    """Get performance metrics for all algorithms."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting all algorithms performance")

        performance = service.get_performance(is_paper=is_paper)

        logger.info(f"[{request_id}] Performance metrics retrieved")

        return {"success": True, "performance": performance}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_performance"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/all")
async def get_all_performance(
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: AlgoService = Depends(get_algo_service)
):
    """Get performance metrics for all algorithms."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting all algorithms performance")

        performance = service.get_performance(is_paper=is_paper)

        logger.info(f"[{request_id}] Performance metrics retrieved")

        return {"success": True, "performance": performance}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_all_performance"})
        raise HTTPException(status_code=500, detail=str(e))
