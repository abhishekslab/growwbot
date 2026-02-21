"""
Trade API routes with comprehensive logging.

Provides CRUD operations for trade management with structured logging.
"""

import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import get_logger, log_error
from core.exceptions import TradeError, ValidationError
from services.trade_service import TradeService
from app.dependencies import get_trade_service

router = APIRouter(prefix="/api/trades", tags=["trades"])
logger = get_logger("api.trades")


@router.get("/")
async def list_trades(
    status: Optional[str] = Query(None, description="Filter by trade status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"),
    service: TradeService = Depends(get_trade_service),
):
    """List all trades with optional filters."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Listing trades - status={status}, symbol={symbol}, is_paper={is_paper}")

        trades = service.list_trades(status=status, symbol=symbol, is_paper=is_paper)

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Found {len(trades)} trades in {duration:.2f}ms")

        return {"success": True, "count": len(trades), "trades": [t.dict() if hasattr(t, "dict") else t for t in trades]}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "list_trades"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_trades_summary(
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: TradeService = Depends(get_trade_service)
):
    """Get trade summary statistics."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Getting trade summary - is_paper={is_paper}")

        summary = service.get_summary(is_paper)

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Summary retrieved in {duration:.2f}ms")

        return {"success": True, "summary": summary.dict() if hasattr(summary, "dict") else summary}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_trades_summary"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_trades_analytics(
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: TradeService = Depends(get_trade_service)
):
    """Get learning analytics for trades."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting trade analytics - is_paper={is_paper}")

        analytics = service.get_learning_analytics(is_paper)

        logger.info(f"[{request_id}] Analytics retrieved")

        return {"success": True, "analytics": analytics}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_trades_analytics"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realized-pnl")
async def get_realized_pnl(
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: TradeService = Depends(get_trade_service)
):
    """Get realized P&L statistics."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting realized PnL - is_paper={is_paper}")

        pnl = service.get_realized_pnl(is_paper)

        logger.info(f"[{request_id}] Realized PnL: {pnl.get('total_pnl', 0)}")

        return {"success": True, "pnl": pnl}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_realized_pnl"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_trades(
    is_paper: Optional[bool] = Query(None, description="Filter by paper trading mode"), service: TradeService = Depends(get_trade_service)
):
    """Get all active (open) trades."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Getting active trades - is_paper={is_paper}")

        trades = service.get_open_trades(is_paper)

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Found {len(trades)} active trades in {duration:.2f}ms")

        return {"success": True, "count": len(trades), "trades": [t.dict() if hasattr(t, "dict") else t for t in trades]}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "get_active_trades"})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trade_id}")
async def get_trade(trade_id: int, service: TradeService = Depends(get_trade_service)):
    """Get a specific trade by ID."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Getting trade #{trade_id}")

        trade = service.get_trade(trade_id)
        if not trade:
            logger.warning(f"[{request_id}] Trade #{trade_id} not found")
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

        logger.info(f"[{request_id}] Trade #{trade_id} found")

        return {"success": True, "trade": trade.dict() if hasattr(trade, "dict") else trade}
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "trade_id": trade_id, "endpoint": "get_trade"})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_trade(trade_data: dict, service: TradeService = Depends(get_trade_service)):
    """Create a new trade."""
    request_id = str(uuid.uuid4())[:8]

    try:
        symbol = trade_data.get("symbol", "UNKNOWN")
        logger.info(f"[{request_id}] Creating trade for {symbol}")

        # Validate required fields
        required = ["symbol", "entry_price", "stop_loss", "target", "quantity"]
        missing = [f for f in required if f not in trade_data]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")

        trade = service.create_trade(trade_data)

        trade_id = trade.id if hasattr(trade, "id") else trade.get("id")
        logger.info(f"[{request_id}] Trade #{trade_id} created for {symbol}")

        return {"success": True, "trade_id": trade_id, "trade": trade.dict() if hasattr(trade, "dict") else trade}
    except ValidationError as e:
        logger.warning(f"[{request_id}] Validation error: {e.message}")
        raise HTTPException(status_code=422, detail=e.message)
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "endpoint": "create_trade"})
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{trade_id}")
async def update_trade(trade_id: int, update_data: dict, service: TradeService = Depends(get_trade_service)):
    """Update an existing trade."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Updating trade #{trade_id}")

        trade = service.update_trade(trade_id, update_data)
        if not trade:
            logger.warning(f"[{request_id}] Trade #{trade_id} not found for update")
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

        logger.info(f"[{request_id}] Trade #{trade_id} updated")

        return {"success": True, "trade": trade.dict() if hasattr(trade, "dict") else trade}
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "trade_id": trade_id, "endpoint": "update_trade"})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/close")
async def close_trade(trade_id: int, close_data: dict, service: TradeService = Depends(get_trade_service)):
    """Close a trade with exit details."""
    request_id = str(uuid.uuid4())[:8]

    try:
        exit_price = close_data.get("exit_price")
        exit_trigger = close_data.get("exit_trigger", "MANUAL")

        logger.info(f"[{request_id}] Closing trade #{trade_id} at {exit_price} ({exit_trigger})")

        if not exit_price:
            raise ValidationError("exit_price is required")

        trade = service.close_trade(trade_id, exit_price, exit_trigger)
        if not trade:
            logger.warning(f"[{request_id}] Trade #{trade_id} not found for closing")
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

        actual_pnl = trade.actual_pnl if hasattr(trade, "actual_pnl") else trade.get("actual_pnl")
        logger.info(f"[{request_id}] Trade #{trade_id} closed with PnL: {actual_pnl}")

        return {"success": True, "trade": trade.dict() if hasattr(trade, "dict") else trade}
    except ValidationError as e:
        logger.warning(f"[{request_id}] Validation error: {e.message}")
        raise HTTPException(status_code=422, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "trade_id": trade_id, "endpoint": "close_trade"})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{trade_id}")
async def delete_trade(trade_id: int, service: TradeService = Depends(get_trade_service)):
    """Delete a trade."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Deleting trade #{trade_id}")

        success = service.delete_trade(trade_id)
        if not success:
            logger.warning(f"[{request_id}] Trade #{trade_id} not found for deletion")
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

        logger.info(f"[{request_id}] Trade #{trade_id} deleted")

        return {"success": True, "message": f"Trade {trade_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "trade_id": trade_id, "endpoint": "delete_trade"})
        raise HTTPException(status_code=500, detail=str(e))
