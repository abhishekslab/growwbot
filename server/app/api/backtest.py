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


class DailyPicksBacktestRequest(BaseModel):
    algo_id: str
    start_date: str
    end_date: str
    candle_interval: str = "5minute"
    initial_capital: float = 100000
    max_positions_per_day: int = 3
    risk_percent: float = 1.0
    max_trade_duration_minutes: int = 15
    use_cached_snapshots: bool = True


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


def _daily_picks_backtest_event_generator(request: DailyPicksBacktestRequest, groww: GrowwClientBase):
    """Generator for SSE daily picks backtest events."""
    import json
    from daily_picks_backtest import run_daily_picks_backtest

    try:
        for event in run_daily_picks_backtest(
            groww=groww,
            start_date=request.start_date,
            end_date=request.end_date,
            algo_id=request.algo_id,
            candle_interval=request.candle_interval,
            initial_capital=request.initial_capital,
            max_positions_per_day=request.max_positions_per_day,
            risk_percent=request.risk_percent,
            max_trade_duration_minutes=request.max_trade_duration_minutes,
            use_cached_snapshots=request.use_cached_snapshots,
        ):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        logger.exception("Daily picks backtest error")
        yield f"data: {json.dumps({'event_type': 'complete', 'error': str(e), 'metrics': {}, 'trades': [], 'equity_curve': []})}\n\n"


# Standard backtest endpoints
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


# Cache management endpoints (must come before /{run_id} routes)
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


# Daily Picks Backtest Endpoints (must come before /{run_id} routes)
@router.post("/daily-picks")
async def run_daily_picks_backtest_endpoint(
    body: DailyPicksBacktestRequest,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Run multi-day full pipeline backtest with daily picks."""
    return StreamingResponse(
        _daily_picks_backtest_event_generator(body, groww),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/cache-daily-picks")
async def cache_daily_picks(
    start_date: str = Query(...),
    end_date: str = Query(...),
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Pre-compute and cache daily picks for a date range."""
    try:
        from historical_screener import run_daily_picks_historical
        from daily_picks_backtest import _get_trading_days

        trading_days = _get_trading_days(start_date, end_date)
        cached = 0
        skipped = 0

        for date in trading_days:
            try:
                result = run_daily_picks_historical(groww, date, use_cached_snapshot=True)
                if result:
                    cached += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning("Failed to cache daily picks for %s: %s", date, e)
                skipped += 1

        return {
            "message": "Daily picks caching complete",
            "cached_dates": cached,
            "skipped": skipped,
            "total": len(trading_days),
            "start_date": start_date,
            "end_date": end_date,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache-daily-picks")
async def clear_daily_picks_cache():
    """Clear all cached daily picks snapshots."""
    try:
        from historical_screener import clear_historical_snapshots

        deleted = clear_historical_snapshots()
        return {"message": "Daily picks cache cleared", "deleted_snapshots": deleted}
    except Exception as e:
        logger.exception("Failed to clear daily picks cache")
        raise HTTPException(status_code=500, detail=str(e))


# FNO endpoints (must come before /{run_id} routes)
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


# Generic /{run_id} routes must come LAST to avoid conflicts with specific routes above
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
