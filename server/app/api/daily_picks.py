"""
Daily Picks API routes.

Provides daily stock picks with SSE streaming for real-time updates.
"""

import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core import get_logger, log_error
from app.dependencies import get_groww_client_dep
from infrastructure.groww_client import GrowwClientBase

router = APIRouter(prefix="/api/daily-picks", tags=["daily-picks"])
logger = get_logger("api.daily-picks")


try:
    from cache import MarketCache

    market_cache = MarketCache()
except ImportError:
    market_cache = None

try:
    from snapshot import load_snapshot, save_snapshot
except ImportError:
    load_snapshot = None
    save_snapshot = None


@router.get("")
async def get_daily_picks(
    limit: int = 10,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Get daily picks (non-streaming)."""
    try:
        from screener import run_daily_picks

        return run_daily_picks(groww, cache=market_cache, limit=limit)
    except Exception as e:
        log_error(logger, e, {"endpoint": "get_daily_picks"})
        raise HTTPException(status_code=500, detail=f"Daily picks failed: {e}")


@router.get("/snapshot")
async def get_daily_picks_snapshot():
    """Get the last saved snapshot."""
    if not load_snapshot:
        raise HTTPException(status_code=500, detail="Snapshot module not available")

    data = load_snapshot()
    if data is None:
        return {"candidates": [], "meta": {}, "saved_at": None}
    return data


@router.get("/stream")
async def stream_daily_picks(
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Stream daily picks via SSE."""
    try:
        from screener import run_daily_picks_streaming
    except ImportError:
        raise HTTPException(status_code=500, detail="Screener module not available")

    def event_generator():
        try:
            last_complete = None
            for update in run_daily_picks_streaming(groww, cache=market_cache):
                yield f"data: {json.dumps(update)}\n\n"
                if update.get("event_type") == "complete":
                    last_complete = update

            if last_complete and save_snapshot:
                try:
                    save_snapshot(last_complete)
                except Exception as e:
                    logger.error("Failed to save snapshot: %s", e)
        except GeneratorExit:
            logger.info("Daily picks stream client disconnected")
        except Exception as e:
            logger.error("SSE stream error: %s", e)
            try:
                yield f"data: {json.dumps({'event_type': 'error', 'message': str(e)})}\n\n"
            except GeneratorExit:
                pass
        finally:
            logger.info("Daily picks stream ended")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/live-ltp")
async def live_ltp_stream(
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Stream live LTP updates via SSE."""
    if not load_snapshot:
        raise HTTPException(status_code=500, detail="Snapshot module not available")

    snapshot = load_snapshot()
    if not snapshot or not snapshot.get("candidates"):
        raise HTTPException(status_code=404, detail="No snapshot available. Run a scan first.")

    candidates = snapshot["candidates"]

    tier1_symbols = []
    tier2_symbols = []
    for c in candidates:
        sym = c["symbol"]
        if c.get("high_conviction") or c.get("meets_gainer_criteria"):
            tier1_symbols.append(sym)
        else:
            tier2_symbols.append(sym)

    def event_generator():
        tick = 0
        consecutive_failures = 0
        max_failures = 10
        base_sleep = 3

        try:
            while True:
                tick += 1
                try:
                    symbols_to_fetch = tier1_symbols.copy()
                    if tick % 5 == 0:
                        symbols_to_fetch.extend(tier2_symbols)

                    if not symbols_to_fetch:
                        time.sleep(base_sleep)
                        continue

                    ltp_updates = {}
                    for i in range(0, len(symbols_to_fetch), 50):
                        batch = symbols_to_fetch[i : i + 50]
                        exchange_syms = tuple(f"NSE_{s}" for s in batch)
                        try:
                            ltp_data = groww.get_ltp(exchange_trading_symbols=exchange_syms, segment="CASH")
                            if isinstance(ltp_data, dict):
                                for key, val in ltp_data.items():
                                    sym = key.replace("NSE_", "")
                                    if isinstance(val, dict):
                                        ltp_updates[sym] = float(val.get("ltp", 0))
                                    else:
                                        ltp_updates[sym] = float(val) if val else 0
                        except Exception as e:
                            logger.warning("LTP fetch failed: %s", e)

                    if ltp_updates:
                        consecutive_failures = 0
                        yield f"data: {json.dumps({'event_type': 'ltp_update', 'updates': ltp_updates, 'tick': tick})}\n\n"
                    else:
                        consecutive_failures += 1

                    if consecutive_failures >= max_failures:
                        yield f"data: {json.dumps({'event_type': 'error', 'message': 'Too many failures'})}\n\n"
                        break

                    time.sleep(base_sleep)

                except Exception as e:
                    logger.error("Live LTP stream error: %s", e)
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        break
                    time.sleep(base_sleep)

        except GeneratorExit:
            logger.info("Live LTP stream client disconnected")
        finally:
            logger.info("Live LTP stream ended")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
