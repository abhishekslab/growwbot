"""
Cache API routes.

Provides cache status, warmup, and clear endpoints.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from core import get_logger, log_error
from cache import MarketCache
from app.dependencies import get_groww_client_dep
from infrastructure.groww_client import GrowwClientBase

router = APIRouter(prefix="/api/cache", tags=["cache"])
logger = get_logger("api.cache")

market_cache = MarketCache()


@router.get("/status")
async def cache_status():
    """Get cache status."""
    try:
        return market_cache.status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache status: {e}")


@router.post("/warmup")
async def cache_warmup(
    background_tasks: BackgroundTasks,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Start cache warmup in background."""
    try:
        background_tasks.add_task(market_cache.warmup, groww)
        return {"message": "Cache warmup started in background"}
    except Exception as e:
        log_error(logger, e, {"endpoint": "cache_warmup"})
        raise HTTPException(status_code=500, detail=f"Failed to start cache warmup: {e}")


@router.post("/clear")
async def cache_clear():
    """Clear the cache."""
    try:
        market_cache.clear()
        return {"message": "Cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")
