"""
Backtest API routes.

Provides backtest running, history, and management endpoints.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core import get_logger, log_error
from app.dependencies import get_groww_client_dep
from infrastructure.groww_client import GrowwClientBase
from strategies.registry import StrategyRegistry

router = APIRouter(prefix="/api/backtest", tags=["backtest"])
logger = get_logger("api.backtest")


class BacktestRunRequest(BaseModel):
    algo_id: str
    groww_symbol: str
    exchange: str = "NSE"
    segment: str = "CASH"
    start_date: str
    end_date: str
    candle_interval: str = "5minute"
    initial_capital: float = 100000
    risk_percent: float = 1.0
    max_positions: int = 1


def _backtest_event_generator(request: BacktestRunRequest, groww: GrowwClientBase):
    """Generator for SSE backtest progress events."""
    import json
    from backtest_engine import run_backtest

    StrategyRegistry.initialize()
    strategy = StrategyRegistry.get(request.algo_id, {})
    if not strategy:
        yield json.dumps(
            {"event_type": "complete", "error": f"Strategy not found: {request.algo_id}", "metrics": {}, "trades": [], "equity_curve": []}
        )
        return

    try:
        for event in run_backtest(
            groww=groww,
            algo=strategy,
            groww_symbol=request.groww_symbol,
            exchange=request.exchange,
            segment=request.segment,
            start_date=request.start_date,
            end_date=request.end_date,
            candle_interval=request.candle_interval,
            initial_capital=request.initial_capital,
            risk_percent=request.risk_percent,
            max_positions=request.max_positions,
        ):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'event_type': 'complete', 'error': str(e), 'metrics': {}, 'trades': [], 'equity_curve': []})}\n\n"


@router.post("/run")
async def run_backtest_endpoint(
    body: BacktestRunRequest,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Run a backtest; streams SSE events (progress, trade, complete)."""
    return StreamingResponse(
        _backtest_event_generator(body, groww),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history")
async def backtest_history(limit: int = Query(50)):
    """Get backtest run history."""
    try:
        from backtest_engine import list_backtest_runs

        return list_backtest_runs(limit=limit)
    except ImportError:
        return {"runs": [], "error": "Backtest engine not available"}


@router.get("/{run_id}")
async def get_backtest(run_id: int):
    """Get a specific backtest run."""
    try:
        from backtest_engine import get_backtest_run

        run = get_backtest_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest run not found")
        return run
    except ImportError:
        raise HTTPException(status_code=500, detail="Backtest engine not available")


@router.delete("/{run_id}")
async def delete_backtest(run_id: int):
    """Delete a backtest run."""
    try:
        from backtest_engine import delete_backtest_run

        if not delete_backtest_run(run_id):
            raise HTTPException(status_code=404, detail="Backtest run not found")
        return {"message": "Deleted"}
    except ImportError:
        raise HTTPException(status_code=500, detail="Backtest engine not available")


@router.get("/expiries")
async def backtest_expiries(
    exchange: str = Query("NSE"),
    underlying_symbol: str = Query(..., alias="underlying"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Get expiries for FNO instruments."""
    try:
        kwargs = {"exchange": exchange, "underlying_symbol": underlying_symbol}
        if year is not None:
            kwargs["year"] = year
        if month is not None:
            kwargs["month"] = month
        result = groww.get_expiries(**kwargs)
        return result if isinstance(result, dict) else {"expiries": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts")
async def backtest_contracts(
    exchange: str = Query("NSE"),
    underlying_symbol: str = Query(..., alias="underlying"),
    expiry_date: str = Query(..., alias="expiry_date"),
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Get contracts for FNO instruments."""
    try:
        result = groww.get_contracts(
            exchange=exchange,
            underlying_symbol=underlying_symbol,
            expiry_date=expiry_date,
        )
        return result if isinstance(result, dict) else {"contracts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/status")
async def backtest_cache_status():
    """Get backtest cache status."""
    try:
        from backtest_engine import backtest_cache_stats

        return backtest_cache_stats()
    except ImportError:
        return {"error": "Backtest engine not available"}


@router.post("/cache/warmup")
async def backtest_cache_warmup(
    groww_symbol: str,
    segment: str = "CASH",
    interval: str = "5minute",
    start_date: str = Query(...),
    end_date: str = Query(...),
    exchange: str = "NSE",
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Warm up backtest cache."""
    try:
        from backtest_engine import backtest_get_candles

        backtest_get_candles(groww, groww_symbol, segment, interval, start_date, end_date, exchange)
        return {"message": "Warmup complete", "symbol": groww_symbol, "start_date": start_date, "end_date": end_date}
    except ImportError:
        raise HTTPException(status_code=500, detail="Backtest engine not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def backtest_cache_clear(groww_symbol: Optional[str] = Query(None)):
    """Clear backtest cache."""
    try:
        from backtest_engine import backtest_clear_cache

        deleted = backtest_clear_cache(groww_symbol)
        return {"message": "Cache cleared", "deleted_entries": deleted}
    except ImportError:
        raise HTTPException(status_code=500, detail="Backtest engine not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
