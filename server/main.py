import os
import asyncio
import json
import time
import logging
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from cache import MarketCache
from snapshot import save_snapshot, load_snapshot
from trades_db import init_db, create_trade, get_trade, list_trades, update_trade, delete_trade, get_summary
from symbol import fetch_candles, fetch_quote, resolve_exchange_token

logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Groww Portfolio API")
market_cache = MarketCache()


@app.on_event("startup")
def startup():
    init_db()


class TradeCreate(BaseModel):
    symbol: str
    trade_type: str = "INTRADAY"
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    capital_used: float
    risk_amount: float
    fees_entry: float = 0
    fees_exit_target: float = 0
    fees_exit_sl: float = 0
    entry_date: Optional[str] = None
    notes: str = ""


class TradeUpdate(BaseModel):
    status: Optional[str] = None
    exit_price: Optional[float] = None
    actual_pnl: Optional[float] = None
    actual_fees: Optional[float] = None
    exit_date: Optional[str] = None
    notes: Optional[str] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_cached_client = None
_cached_client_time = 0
_TOKEN_TTL = 300  # re-auth every 5 minutes


def get_groww_client():
    global _cached_client, _cached_client_time
    now = time.time()
    if _cached_client and (now - _cached_client_time) < _TOKEN_TTL:
        return _cached_client

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=500,
            detail="API_KEY and API_SECRET must be set in server/.env",
        )
    from growwapi import GrowwAPI

    access_token = GrowwAPI.get_access_token(api_key, secret=api_secret)
    _cached_client = GrowwAPI(access_token)
    _cached_client_time = now
    return _cached_client


@app.get("/api/holdings")
def get_holdings():
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        response = groww.get_holdings_for_user()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch holdings: {e}")

    raw_holdings = response.get("holdings", []) if isinstance(response, dict) else response

    holdings = []
    total_current = 0.0
    total_invested = 0.0

    # Build exchange symbols for batch LTP fetch
    exchange_symbols = []
    for h in raw_holdings:
        ts = h.get("trading_symbol", "UNKNOWN")
        exchanges = h.get("tradable_exchanges", ["NSE"])
        exchange = exchanges[0] if exchanges else "NSE"
        exchange_symbols.append(f"{exchange}_{ts}")

    ltp_map: dict = {}
    if exchange_symbols:
        try:
            ltp_data = groww.get_ltp(
                exchange_trading_symbols=tuple(exchange_symbols),
                segment="CASH",
            )
            # Response is {"NSE_SYMBOL": 123.45, ...}
            if isinstance(ltp_data, dict):
                for key, val in ltp_data.items():
                    if isinstance(val, dict):
                        ltp_map[key] = float(val.get("ltp", 0))
                    else:
                        ltp_map[key] = float(val)
        except Exception:
            pass

    for i, h in enumerate(raw_holdings):
        symbol = h.get("trading_symbol", "UNKNOWN")
        quantity = float(h.get("quantity", 0))
        average_price = float(h.get("average_price", 0))

        es = exchange_symbols[i] if i < len(exchange_symbols) else ""
        ltp = ltp_map.get(es, average_price)

        current_value = quantity * ltp
        invested_value = quantity * average_price
        pnl = current_value - invested_value
        pnl_percentage = (pnl / invested_value * 100) if invested_value != 0 else 0.0

        total_current += current_value
        total_invested += invested_value

        holdings.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "average_price": round(average_price, 2),
                "ltp": round(ltp, 2),
                "current_value": round(current_value, 2),
                "invested_value": round(invested_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percentage": round(pnl_percentage, 2),
            }
        )

    total_pnl = total_current - total_invested
    total_pnl_percentage = (
        (total_pnl / total_invested * 100) if total_invested != 0 else 0.0
    )

    return {
        "holdings": holdings,
        "summary": {
            "total_current_value": round(total_current, 2),
            "total_invested_value": round(total_invested, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percentage": round(total_pnl_percentage, 2),
        },
    }


@app.get("/api/daily-picks")
def get_daily_picks(limit: int = 10):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        from screener import run_daily_picks

        return run_daily_picks(groww, cache=market_cache, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Daily picks failed: {e}")


@app.get("/api/daily-picks/snapshot")
def get_daily_picks_snapshot():
    data = load_snapshot()
    if data is None:
        return {"candidates": [], "meta": {}, "saved_at": None}
    return data


@app.get("/api/daily-picks/stream")
def stream_daily_picks():
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    from screener import run_daily_picks_streaming

    def event_generator():
        try:
            last_complete = None
            for update in run_daily_picks_streaming(groww, cache=market_cache):
                yield f"data: {json.dumps(update)}\n\n"
                if update.get("event_type") == "complete":
                    last_complete = update
            # Save snapshot to disk after scan completes
            if last_complete:
                try:
                    save_snapshot(last_complete)
                except Exception as e:
                    logger.error("Failed to save snapshot: %s", e)
        except Exception as e:
            logger.error("SSE stream error: %s", e)
            yield f"data: {json.dumps({'event_type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/daily-picks/live-ltp")
def live_ltp_stream():
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    snapshot = load_snapshot()
    if not snapshot or not snapshot.get("candidates"):
        raise HTTPException(status_code=404, detail="No snapshot available. Run a scan first.")

    candidates = snapshot["candidates"]

    # Classify into tiers
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
        try:
            while True:
                # Tier 1 every tick (~3s), Tier 2 every 5th tick (~15s)
                symbols_this_tick = list(tier1_symbols)
                if tick % 5 == 0:
                    symbols_this_tick.extend(tier2_symbols)

                if not symbols_this_tick:
                    time.sleep(3)
                    tick += 1
                    continue

                # Fetch LTP in batches of 50
                updates = {}
                for i in range(0, len(symbols_this_tick), 50):
                    batch_syms = symbols_this_tick[i : i + 50]
                    exchange_syms = tuple(f"NSE_{s}" for s in batch_syms)
                    try:
                        ltp_data = groww.get_ltp(
                            exchange_trading_symbols=exchange_syms, segment="CASH"
                        )
                        if isinstance(ltp_data, dict):
                            for key, val in ltp_data.items():
                                sym = key.replace("NSE_", "", 1)
                                if isinstance(val, dict):
                                    price = float(val.get("ltp", 0))
                                else:
                                    price = float(val) if val else 0
                                if price > 0:
                                    # Find open price from snapshot to compute day_change_pct
                                    open_price = 0
                                    for c in candidates:
                                        if c["symbol"] == sym:
                                            open_price = c.get("open", 0)
                                            break
                                    day_change_pct = (
                                        round(((price - open_price) / open_price) * 100, 2)
                                        if open_price > 0
                                        else 0
                                    )
                                    updates[sym] = {
                                        "ltp": round(price, 2),
                                        "day_change_pct": day_change_pct,
                                    }
                    except Exception as e:
                        logger.warning("Live LTP batch failed: %s", e)

                if updates:
                    # Store in cache
                    ltp_cache_map = {f"NSE_{s}": v["ltp"] for s, v in updates.items()}
                    market_cache.update_ltp_batch(ltp_cache_map)

                    event = {
                        "event_type": "ltp_update",
                        "updates": updates,
                        "timestamp": time.time(),
                    }
                    yield f"data: {json.dumps(event)}\n\n"

                time.sleep(3)
                tick += 1
        except GeneratorExit:
            logger.info("Live LTP stream client disconnected")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/screener")
def get_screener():
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        from screener import run_daily_picks

        return run_daily_picks(groww, cache=market_cache)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screener failed: {e}")


@app.get("/api/top-movers")
def get_top_movers(limit: int = 50):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        from screener import run_top_movers

        return run_top_movers(groww, cache=market_cache, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Top movers failed: {e}")


@app.get("/api/cache/status")
def cache_status():
    return market_cache.status()


@app.post("/api/cache/warmup")
def cache_warmup(background_tasks: BackgroundTasks):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    background_tasks.add_task(market_cache.warmup, groww)
    return {"message": "Cache warmup started in background"}


@app.post("/api/cache/clear")
def cache_clear():
    market_cache.clear()
    return {"message": "Cache cleared"}


# ------------------------------------------------------------------
# LTP endpoint
# ------------------------------------------------------------------
@app.get("/api/ltp/{symbol}")
def get_ltp(symbol: str):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        exchange_symbol = f"NSE_{symbol}"
        ltp_data = groww.get_ltp(
            exchange_trading_symbols=(exchange_symbol,), segment="CASH"
        )
        if isinstance(ltp_data, dict):
            val = ltp_data.get(exchange_symbol)
            if isinstance(val, dict):
                price = float(val.get("ltp", 0))
            else:
                price = float(val) if val else 0
        else:
            price = 0
        return {"symbol": symbol, "ltp": price}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch LTP: {e}")


# ------------------------------------------------------------------
# Trade CRUD endpoints
# ------------------------------------------------------------------
@app.post("/api/trades")
def api_create_trade(body: TradeCreate):
    data = body.model_dump(exclude_none=True)
    trade = create_trade(data)
    return trade


@app.get("/api/trades/summary")
def api_trades_summary():
    return get_summary()


@app.get("/api/trades")
def api_list_trades(
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
):
    return list_trades(status=status, symbol=symbol)


@app.get("/api/trades/{trade_id}")
def api_get_trade(trade_id: int):
    trade = get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@app.patch("/api/trades/{trade_id}")
def api_update_trade(trade_id: int, body: TradeUpdate):
    data = body.model_dump(exclude_none=True)
    trade = update_trade(trade_id, data)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@app.delete("/api/trades/{trade_id}")
def api_delete_trade(trade_id: int):
    if not delete_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"message": "Trade deleted"}


# ------------------------------------------------------------------
# Symbol detail endpoints
# ------------------------------------------------------------------
@app.get("/api/candles/{symbol}")
def get_candles(symbol: str, interval: str = "5minute", days: int = 5):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        candles = fetch_candles(groww, symbol, interval=interval, days=days)
        return {"candles": candles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch candles: {e}")


@app.get("/api/quote/{symbol}")
def get_quote(symbol: str):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        return fetch_quote(groww, symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {e}")


class OrderRequest(BaseModel):
    trading_symbol: str
    transaction_type: str  # BUY or SELL
    order_type: str  # MARKET, LIMIT, SL, SL-M
    product: str  # CNC, MIS, NRML
    quantity: int
    price: float = 0.0
    trigger_price: Optional[float] = None
    validity: str = "DAY"


@app.post("/api/order")
def place_order(body: OrderRequest):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        result = groww.place_order(
            validity=body.validity,
            exchange="NSE",
            order_type=body.order_type,
            product=body.product,
            quantity=body.quantity,
            segment="CASH",
            trading_symbol=body.trading_symbol,
            transaction_type=body.transaction_type,
            price=body.price,
            trigger_price=body.trigger_price,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order failed: {e}")


@app.websocket("/ws/ltp/{symbol}")
async def ws_ltp(websocket: WebSocket, symbol: str):
    await websocket.accept()
    feed = None
    try:
        groww = get_groww_client()
        token = await asyncio.get_event_loop().run_in_executor(
            None, resolve_exchange_token, groww, symbol
        )
        if not token:
            await websocket.send_json({"error": "Could not resolve exchange token"})
            await websocket.close()
            return

        from growwapi import GrowwFeed

        feed = await asyncio.get_event_loop().run_in_executor(
            None, GrowwFeed, groww
        )
        instrument_list = [{"exchange": "NSE", "segment": "CASH", "exchange_token": token}]
        await asyncio.get_event_loop().run_in_executor(
            None, feed.subscribe_ltp, instrument_list
        )

        while True:
            ltp_data = await asyncio.get_event_loop().run_in_executor(
                None, feed.get_ltp
            )
            # Navigate nested structure: {"NSE": {"CASH": {token: {...}}}}
            price = None
            if isinstance(ltp_data, dict):
                nse = ltp_data.get("NSE", {})
                if isinstance(nse, dict):
                    cash = nse.get("CASH", {})
                    if isinstance(cash, dict):
                        token_data = cash.get(token, cash.get(str(token), {}))
                        if isinstance(token_data, dict):
                            price = token_data.get("ltp", token_data.get("last_price"))
                        elif isinstance(token_data, (int, float)):
                            price = token_data
            if price is not None:
                await websocket.send_json({"symbol": symbol, "ltp": float(price)})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error for %s: %s", symbol, e)
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        if feed:
            try:
                await asyncio.get_event_loop().run_in_executor(None, feed.close)
            except Exception:
                pass
