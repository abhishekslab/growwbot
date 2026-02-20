import asyncio
import json
import logging
import os
import threading
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from algo_engine import AlgoEngine
from algo_mean_reversion import MeanReversion
from algo_momentum import MomentumScalping
from cache import MarketCache
from position_monitor import PositionMonitor, compute_exit_pnl
from snapshot import load_snapshot, save_snapshot
from symbol import fetch_candles, fetch_quote, resolve_exchange_token
from trades_db import (
    create_trade,
    delete_trade,
    get_algo_performance,
    get_learning_analytics,
    get_realized_pnl,
    get_summary,
    get_trade,
    init_db,
    list_algo_signals,
    list_trades,
    update_trade,
)

logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="GrowwBot API")
market_cache = MarketCache()
monitor = PositionMonitor()
algo_engine = AlgoEngine()
algo_engine.register_algo(MomentumScalping(algo_engine._config))
algo_engine.register_algo(MeanReversion(algo_engine._config))


@app.on_event("startup")
def startup():
    init_db()
    _ensure_token()
    monitor.start()
    algo_engine.start()


@app.on_event("shutdown")
def shutdown():
    algo_engine.stop()
    monitor.stop()


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
    is_paper: bool = False
    entry_snapshot: Optional[str] = None


class TradeUpdate(BaseModel):
    status: Optional[str] = None
    exit_price: Optional[float] = None
    actual_pnl: Optional[float] = None
    actual_fees: Optional[float] = None
    exit_date: Optional[str] = None
    notes: Optional[str] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    exit_trigger: Optional[str] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error: %s" % exc},
    )


_cached_client = None
_cached_client_time = 0
_TOKEN_TTL = 8 * 3600  # 8 hours
_TOKEN_FILE = os.path.join(os.path.dirname(__file__) or ".", ".groww_token")
_auth_lock = threading.Lock()
_auth_fail_time = 0  # timestamp of last auth failure
_AUTH_COOLDOWN = 300  # don't retry auth for 5 minutes after failure


def _save_token(access_token):
    """Persist token to disk so server restarts / --reload reuse it."""
    try:
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_TOKEN_FILE) or ".")
        with os.fdopen(fd, "w") as f:
            json.dump({"token": access_token, "time": time.time()}, f)
        os.replace(tmp, _TOKEN_FILE)
    except Exception as e:
        logger.warning("Could not save token to disk: %s", e)


def _load_token():
    """Load persisted token from disk. Returns (token, timestamp) or (None, 0)."""
    try:
        with open(_TOKEN_FILE) as f:
            data = json.load(f)
        token = data["token"]
        token_time = float(data["time"])
        if (time.time() - token_time) < _TOKEN_TTL:
            return token, token_time
    except Exception:
        pass
    return None, 0


def _ensure_token():
    """Obtain a valid token at startup, retrying on rate limits."""
    global _cached_client, _cached_client_time, _auth_fail_time

    # 1. Try loading persisted token from disk
    saved_token, saved_time = _load_token()
    if saved_token:
        from growwapi import GrowwAPI
        _cached_client = GrowwAPI(saved_token)
        _cached_client_time = saved_time
        logger.info("Startup: loaded persisted token (age %.0fs)", time.time() - saved_time)
        return

    # 2. Generate fresh token with rate-limit retries
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        logger.critical("Startup: API_KEY/API_SECRET not set in server/.env — cannot start")
        raise SystemExit(1)

    from growwapi import GrowwAPI
    max_retries = 5
    retry_interval = 60

    for attempt in range(1, max_retries + 1):
        try:
            access_token = GrowwAPI.get_access_token(api_key, secret=api_secret)
            _cached_client = GrowwAPI(access_token)
            _cached_client_time = time.time()
            _auth_fail_time = 0
            _save_token(access_token)
            logger.info("Startup: token obtained and persisted")
            return
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(k in err_str for k in ("rate", "limit", "429", "too many"))
            if is_rate_limit and attempt < max_retries:
                logger.warning("Startup: rate limited (attempt %d/%d), retrying in %ds...",
                               attempt, max_retries, retry_interval)
                time.sleep(retry_interval)
            else:
                logger.warning("Startup: auth failed: %s — deferring to lazy auth", e)
                return


def get_groww_client():
    global _cached_client, _cached_client_time
    now = time.time()

    # Fast path: in-memory cached client still valid
    if _cached_client and (now - _cached_client_time) < _TOKEN_TTL:
        return _cached_client

    with _auth_lock:
        # Double-check after acquiring lock
        now = time.time()
        if _cached_client and (now - _cached_client_time) < _TOKEN_TTL:
            return _cached_client

        from growwapi import GrowwAPI

        # 1. Try loading persisted token from disk (survives --reload / restart)
        saved_token, saved_time = _load_token()
        if saved_token:
            logger.info("Loaded persisted token from disk (age %.0fs)", now - saved_time)
            _cached_client = GrowwAPI(saved_token)
            _cached_client_time = saved_time
            return _cached_client

        # 2. No persisted token — must authenticate
        #    But if auth failed recently, don't hammer the endpoint
        if _auth_fail_time and (now - _auth_fail_time) < _AUTH_COOLDOWN:
            wait = int(_AUTH_COOLDOWN - (now - _auth_fail_time))
            raise HTTPException(
                status_code=503,
                detail="Auth rate-limited. Retry in %ds, or run: python3 get_token.py" % wait,
            )

        api_key = os.getenv("API_KEY")
        api_secret = os.getenv("API_SECRET")
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=500,
                detail="API_KEY and API_SECRET must be set in server/.env",
            )

        try:
            access_token = GrowwAPI.get_access_token(api_key, secret=api_secret)
            _cached_client = GrowwAPI(access_token)
            _cached_client_time = time.time()
            _auth_fail_time = 0  # reset on success
            _save_token(access_token)
            logger.info("Groww auth successful, token persisted to disk")
            return _cached_client
        except Exception as e:
            logger.warning("Auth failed: %s", e)
            _auth_fail_time = time.time()

            # Return stale in-memory client if one exists
            if _cached_client:
                logger.warning(
                    "Returning stale client (age %.0fs)",
                    time.time() - _cached_client_time,
                )
                return _cached_client

            raise HTTPException(
                status_code=503,
                detail="Authentication failed: %s. Run: python3 get_token.py" % e,
            )


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
        consecutive_failures = 0
        max_failures = 10
        base_sleep = 3
        try:
            while True:
                # Tier 1 every tick (~3s), Tier 2 every 5th tick (~15s)
                symbols_this_tick = list(tier1_symbols)
                if tick % 5 == 0:
                    symbols_this_tick.extend(tier2_symbols)

                if not symbols_this_tick:
                    time.sleep(base_sleep)
                    tick += 1
                    continue

                # Fetch LTP in batches of 50
                updates = {}
                batch_had_error = False
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
                        batch_had_error = True

                if updates:
                    # Success — reset failure counter
                    consecutive_failures = 0

                    # Store in cache
                    ltp_cache_map = {f"NSE_{s}": v["ltp"] for s, v in updates.items()}
                    market_cache.update_ltp_batch(ltp_cache_map)

                    event = {
                        "event_type": "ltp_update",
                        "updates": updates,
                        "timestamp": time.time(),
                    }
                    yield f"data: {json.dumps(event)}\n\n"
                elif batch_had_error:
                    consecutive_failures += 1
                    logger.warning(
                        "Live LTP: %d consecutive failures (max %d)",
                        consecutive_failures, max_failures,
                    )
                    if consecutive_failures >= max_failures:
                        logger.error(
                            "Live LTP circuit breaker tripped after %d failures",
                            consecutive_failures,
                        )
                        yield f"data: {json.dumps({'event_type': 'error', 'message': 'API unavailable — stream stopped after %d consecutive failures' % consecutive_failures})}\n\n"
                        break

                # Backoff: 3s normally, up to 30s on consecutive failures
                sleep_time = min(base_sleep * (2 ** min(consecutive_failures, 3)), 30)
                time.sleep(sleep_time)
                tick += 1
        except GeneratorExit:
            logger.info("Live LTP stream client disconnected")
        except Exception as e:
            logger.error("Live LTP stream unexpected error: %s", e)
            try:
                yield f"data: {json.dumps({'event_type': 'error', 'message': str(e)})}\n\n"
            except GeneratorExit:
                pass

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
    if body.is_paper:
        data["is_paper"] = 1
        data["order_status"] = "SIMULATED"
    else:
        data.pop("is_paper", None)
    trade = create_trade(data)
    return trade


@app.get("/api/trades/summary")
def api_trades_summary(is_paper: Optional[bool] = Query(None)):
    return get_summary(is_paper=is_paper)


@app.get("/api/trades/analytics")
def api_trade_analytics(is_paper: Optional[bool] = Query(None)):
    return get_learning_analytics(is_paper=is_paper)


@app.get("/api/trades/realized-pnl")
def api_realized_pnl(is_paper: Optional[bool] = Query(None)):
    return get_realized_pnl(is_paper=is_paper)


@app.get("/api/trades")
def api_list_trades(
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    is_paper: Optional[bool] = Query(None),
):
    return list_trades(status=status, symbol=symbol, is_paper=is_paper)


@app.get("/api/trades/active")
def get_active_trades(is_paper: Optional[bool] = Query(None)):
    open_trades = list_trades(status="OPEN", is_paper=is_paper)
    if not open_trades:
        return []

    # Batch fetch LTP
    symbols = list(set(t["symbol"] for t in open_trades))
    ltp_map = {}  # type: dict
    try:
        groww = get_groww_client()
        for i in range(0, len(symbols), 50):
            batch = symbols[i:i + 50]
            exchange_syms = tuple("NSE_%s" % s for s in batch)
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
                            ltp_map[sym] = price
            except Exception:
                pass
    except Exception:
        pass

    result = []
    for t in open_trades:
        ltp = ltp_map.get(t["symbol"], 0)
        entry = t["entry_price"]
        qty = t["quantity"]
        target = t["target"]
        sl = t["stop_loss"]
        unrealized_pnl = (ltp - entry) * qty if ltp > 0 else 0
        distance_to_target_pct = round((target - ltp) / ltp * 100, 2) if ltp > 0 else 0
        distance_to_sl_pct = round((ltp - sl) / ltp * 100, 2) if ltp > 0 else 0
        result.append({
            **t,
            "current_ltp": ltp,
            "unrealized_pnl": round(unrealized_pnl, 2),
            "distance_to_target_pct": distance_to_target_pct,
            "distance_to_sl_pct": distance_to_sl_pct,
        })
    return result


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
# Buy + Monitor endpoints
# ------------------------------------------------------------------

class BuyTradeRequest(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    capital_used: float
    risk_amount: float
    fees_entry: float = 0
    fees_exit_target: float = 0
    fees_exit_sl: float = 0
    trade_type: str = "DELIVERY"
    is_paper: bool = False
    entry_snapshot: Optional[str] = None


@app.post("/api/trades/buy")
def buy_and_monitor(body: BuyTradeRequest):
    trade_data = {
        "symbol": body.symbol,
        "trade_type": body.trade_type,
        "entry_price": body.entry_price,
        "stop_loss": body.stop_loss,
        "target": body.target,
        "quantity": body.quantity,
        "capital_used": body.capital_used,
        "risk_amount": body.risk_amount,
        "fees_entry": body.fees_entry,
        "fees_exit_target": body.fees_exit_target,
        "fees_exit_sl": body.fees_exit_sl,
    }
    if body.entry_snapshot:
        trade_data["entry_snapshot"] = body.entry_snapshot

    # --- Paper trade path: skip broker entirely ---
    if body.is_paper:
        trade_data["is_paper"] = 1
        trade_data["order_status"] = "SIMULATED"
        trade = create_trade(trade_data)
        logger.info("Paper trade #%s created for %s", trade["id"], body.symbol)
        return {"order": {"status": "SIMULATED"}, "trade": trade}

    # --- Real trade path ---
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Authentication failed: %s" % e)

    # 1. Place LIMIT BUY order
    try:
        order_result = groww.place_order(
            validity="DAY",
            exchange="NSE",
            order_type="LIMIT",
            product="CNC",
            quantity=body.quantity,
            segment="CASH",
            trading_symbol=body.symbol,
            transaction_type="BUY",
            price=body.entry_price,
        )
    except Exception as e:
        # Record the failed order attempt so it shows in trade history
        trade_data["status"] = "FAILED"
        trade_data["order_status"] = "REJECTED"
        trade_data["notes"] = "BUY order failed: %s" % e
        trade = create_trade(trade_data)
        return JSONResponse(
            status_code=500,
            content={"detail": "Order failed: %s" % e, "trade": trade},
        )

    # 2. Extract groww_order_id from response
    groww_order_id = None
    if isinstance(order_result, dict):
        groww_order_id = order_result.get("groww_order_id") or order_result.get("orderId")

    # 3. Create trade in ledger
    trade_data["order_status"] = "PLACED"
    trade_data["groww_order_id"] = groww_order_id
    trade = create_trade(trade_data)

    # 4. Verify order status after a brief delay (exchange may reject quickly)
    if groww_order_id:
        def _verify_order_status():
            time.sleep(3)
            try:
                status_resp = groww.get_order_status(
                    segment="CASH", groww_order_id=groww_order_id,
                )
                order_status = ""
                if isinstance(status_resp, dict):
                    order_status = status_resp.get("status", "").upper()
                if order_status in ("REJECTED", "CANCELLED"):
                    reason = ""
                    if isinstance(status_resp, dict):
                        reason = status_resp.get("rejection_reason", "") or status_resp.get("message", "")
                    update_trade(trade["id"], {
                        "status": "FAILED",
                        "order_status": order_status,
                        "notes": "Order %s: %s" % (order_status.lower(), reason),
                    })
                    logger.warning(
                        "Order %s for trade #%s %s was %s: %s",
                        groww_order_id, trade["id"], trade_data["symbol"],
                        order_status, reason,
                    )
            except Exception as e:
                logger.warning("Failed to verify order status for %s: %s", groww_order_id, e)
        threading.Thread(target=_verify_order_status, daemon=True).start()

    # 5. Monitor picks it up automatically (reads OPEN trades from DB)
    return {"order": order_result, "trade": trade}


@app.post("/api/trades/{trade_id}/close")
def close_trade_position(trade_id: int):
    trade = get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade["status"] != "OPEN":
        raise HTTPException(status_code=400, detail="Trade is not OPEN")

    is_paper = trade.get("is_paper")

    if not is_paper:
        try:
            groww = get_groww_client()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Authentication failed: %s" % e)

    # Fetch current LTP for exit price
    exit_price = 0.0
    try:
        groww_for_ltp = get_groww_client() if is_paper else groww
        exchange_symbol = "NSE_%s" % trade["symbol"]
        ltp_data = groww_for_ltp.get_ltp(
            exchange_trading_symbols=(exchange_symbol,), segment="CASH"
        )
        if isinstance(ltp_data, dict):
            val = ltp_data.get(exchange_symbol)
            if isinstance(val, dict):
                exit_price = float(val.get("ltp", 0))
            else:
                exit_price = float(val) if val else 0
    except Exception:
        pass

    # Place MARKET SELL (skip for paper trades)
    if not is_paper:
        try:
            groww.place_order(
                validity="DAY",
                exchange="NSE",
                order_type="MARKET",
                product="CNC",
                quantity=trade["quantity"],
                segment="CASH",
                trading_symbol=trade["symbol"],
                transaction_type="SELL",
                price=0,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail="SELL order failed: %s" % e)

    trade_type = trade.get("trade_type", "DELIVERY")
    net_pnl, total_fees = compute_exit_pnl(
        trade["entry_price"], exit_price, trade["quantity"], trade_type,
    )

    from datetime import datetime as dt
    from datetime import timezone as tz
    now = dt.now(tz.utc).isoformat()

    updated = update_trade(trade_id, {
        "status": "CLOSED",
        "exit_price": round(exit_price, 2),
        "actual_pnl": net_pnl,
        "actual_fees": total_fees,
        "exit_date": now,
        "exit_trigger": "MANUAL",
    })
    return updated


# ------------------------------------------------------------------
# Algo engine endpoints
# ------------------------------------------------------------------

@app.get("/api/algos")
def api_list_algos():
    """List all algos with status + summary."""
    status = algo_engine.get_status()
    # Enrich each algo with trade counts
    for algo in status["algos"]:
        algo_id = algo["algo_id"]
        open_trades = list_trades(status="OPEN", is_paper=True, algo_id=algo_id)
        algo["open_trades"] = len(open_trades)
    return status


@app.post("/api/algos/{algo_id}/start")
def api_start_algo(algo_id: str):
    if algo_engine.start_algo(algo_id):
        return {"message": "Algo %s enabled" % algo_id, "algo_id": algo_id, "enabled": True}
    raise HTTPException(status_code=404, detail="Algo not found: %s" % algo_id)


@app.post("/api/algos/{algo_id}/stop")
def api_stop_algo(algo_id: str):
    if algo_engine.stop_algo(algo_id):
        return {"message": "Algo %s disabled" % algo_id, "algo_id": algo_id, "enabled": False}
    raise HTTPException(status_code=404, detail="Algo not found: %s" % algo_id)


class AlgoSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    capital: Optional[float] = None
    risk_percent: Optional[float] = None
    compounding: Optional[bool] = None


@app.patch("/api/algos/{algo_id}/settings")
def api_update_algo_settings(algo_id: str, body: AlgoSettingsUpdate):
    data = {}
    if body.enabled is not None:
        data["enabled"] = body.enabled
    if body.capital is not None:
        if body.capital <= 0:
            raise HTTPException(status_code=400, detail="Capital must be positive")
        data["capital"] = body.capital
    if body.risk_percent is not None:
        if body.risk_percent <= 0 or body.risk_percent > 100:
            raise HTTPException(status_code=400, detail="Risk percent must be between 0 and 100")
        data["risk_percent"] = body.risk_percent
    if body.compounding is not None:
        data["compounding"] = 1 if body.compounding else 0
    if not data:
        raise HTTPException(status_code=400, detail="No settings to update")
    result = algo_engine.update_algo_settings(algo_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail="Algo not found: %s" % algo_id)
    return result


@app.get("/api/algos/performance")
def api_algo_performance(is_paper: Optional[bool] = Query(None), by_version: bool = Query(False)):
    return get_algo_performance(is_paper=is_paper, group_by_version=by_version)


@app.get("/api/algos/{algo_id}/signals")
def api_algo_signals(algo_id: str, limit: int = Query(50)):
    return list_algo_signals(algo_id=algo_id, limit=limit)


# ------------------------------------------------------------------
# Symbol detail endpoints
# ------------------------------------------------------------------
def _aggregate_candles(candles, factor):
    # type: (list, int) -> list
    """Aggregate 1-minute candles into N-minute candles."""
    aggregated = []
    for i in range(0, len(candles), factor):
        group = candles[i:i + factor]
        if not group:
            break
        aggregated.append({
            "time": group[0]["time"],
            "open": group[0]["open"],
            "high": max(c["high"] for c in group),
            "low": min(c["low"] for c in group),
            "close": group[-1]["close"],
            "volume": sum(c["volume"] for c in group),
        })
    return aggregated


@app.get("/api/candles/{symbol}")
def get_candles(symbol: str, interval: str = "5minute", days: int = 5):
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        if interval == "3minute":
            candles = fetch_candles(groww, symbol, interval="1minute", days=days)
            candles = _aggregate_candles(candles, 3)
        else:
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
                    symbol, consecutive_timeouts, max_timeouts,
                )
                if consecutive_timeouts >= max_timeouts:
                    logger.error(
                        "WebSocket closing for %s after %d consecutive timeouts",
                        symbol, max_timeouts,
                    )
                    await websocket.send_json({
                        "error": "Feed timed out %d times — closing" % max_timeouts,
                    })
                    break
                await asyncio.sleep(1)
                continue

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
