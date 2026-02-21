"""
WebSocket API routes.

Provides real-time LTP streaming via WebSocket.
"""

import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from core import get_logger
from app.dependencies import get_groww_client_dep
from infrastructure.groww_client import GrowwClientBase
from symbol import resolve_exchange_token

router = APIRouter(tags=["websocket"])
logger = get_logger("api.websocket")


@router.websocket("/ws/ltp/{symbol}")
async def ws_ltp(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for real-time LTP streaming."""
    await websocket.accept()
    feed = None
    try:
        groww = get_groww_client_dep()
        token = await asyncio.get_event_loop().run_in_executor(None, resolve_exchange_token, groww, symbol)
        if not token:
            await websocket.send_json({"error": "Could not resolve exchange token"})
            await websocket.close()
            return

        from growwapi import GrowwFeed

        feed = await asyncio.get_event_loop().run_in_executor(None, GrowwFeed, groww)
        instrument_list = [{"exchange": "NSE", "segment": "CASH", "exchange_token": token}]
        await asyncio.get_event_loop().run_in_executor(None, feed.subscribe_ltp, instrument_list)

        consecutive_timeouts = 0
        max_timeouts = 10
        while True:
            try:
                ltp_data = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, feed.get_ltp),
                    timeout=10,
                )
                consecutive_timeouts = 0
            except asyncio.TimeoutError:
                consecutive_timeouts += 1
                logger.warning(
                    "WebSocket feed.get_ltp timeout for %s (%d/%d)",
                    symbol,
                    consecutive_timeouts,
                    max_timeouts,
                )
                if consecutive_timeouts >= max_timeouts:
                    logger.error(
                        "WebSocket closing for %s after %d consecutive timeouts",
                        symbol,
                        max_timeouts,
                    )
                    await websocket.send_json(
                        {
                            "error": "Feed timed out %d times — closing" % max_timeouts,
                        }
                    )
                    break
                await asyncio.sleep(1)
                continue

            price = None
            if isinstance(ltp_data, dict):
                nse = ltp_data.get("NSE", {})
                if isinstance(nse, dict):
                    cash = nse.get("CASH", {})
                    if isinstance(cash, dict):
                        price_data = cash.get(token, {})
                        if isinstance(price_data, dict):
                            price = price_data.get("ltp")

            if price is not None:
                await websocket.send_json(
                    {
                        "symbol": symbol,
                        "ltp": price,
                    }
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for %s", symbol)
    except Exception as e:
        logger.error("WebSocket error for %s: %s", symbol, e)
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        if feed:
            try:
                feed.unsubscribe_ltp()
            except Exception:
                pass
