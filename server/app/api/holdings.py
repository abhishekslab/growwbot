"""
Holdings API routes.

Provides portfolio holdings with enriched LTP and P&L data.
"""

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import get_logger, log_error
from core.exceptions import HoldingsError
from services.holdings_service import HoldingsService, HoldingsError as ServiceHoldingsError
from app.dependencies import get_holdings_service

router = APIRouter(prefix="/api/holdings", tags=["holdings"])
logger = get_logger("api.holdings")


@router.get("")
async def get_holdings(
    service: HoldingsService = Depends(get_holdings_service),
):
    """Get user portfolio holdings with real-time LTP and P&L."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Fetching holdings")

        result = service.get_holdings()

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Retrieved {len(result.get('holdings', []))} holdings in {duration:.2f}ms")

        return result

    except ServiceHoldingsError as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_holdings"})
        raise HTTPException(status_code=500, detail=str(e))
    except HoldingsError as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_holdings"})
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_holdings"})
        raise HTTPException(status_code=500, detail=f"Failed to fetch holdings: {e}")
