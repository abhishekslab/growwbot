"""
Symbol API routes.

Provides candles, quotes, and LTP endpoints for symbols.
"""

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import get_logger, log_error
from app.dependencies import get_groww_client_dep
from infrastructure.groww_client import GrowwClientBase
import pandas as pd

router = APIRouter(prefix="/api", tags=["symbols"])
logger = get_logger("api.symbols")


class OrderRequest(BaseModel):
    trading_symbol: str
    transaction_type: str
    order_type: str
    product: str
    quantity: int
    price: float = 0.0
    trigger_price: Optional[float] = None
    validity: str = "DAY"


def _aggregate_candles(candles: list, n: int) -> list:
    """Aggregate 1-minute candles into n-minute candles."""
    aggregated = []
    for i in range(0, len(candles), n):
        group = candles[i : i + n]
        if not group:
            continue
        aggregated.append(
            {
                "time": group[0]["time"],
                "open": group[0]["open"],
                "high": max(c["high"] for c in group),
                "low": min(c["low"] for c in group),
                "close": group[-1]["close"],
                "volume": sum(c["volume"] for c in group),
            }
        )
    return aggregated


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    interval: str = Query("5minute", description="Candle interval"),
    days: int = Query(5, description="Number of days"),
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Get historical candles for a symbol."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Fetching candles for {symbol}, interval={interval}, days={days}")

        try:
            from symbol import fetch_candles

            if interval == "3minute":
                candles = fetch_candles(groww, symbol, interval="1minute", days=days)
                candles = _aggregate_candles(candles, 3)
            else:
                candles = fetch_candles(groww, symbol, interval=interval, days=days)
        except ImportError:
            candles = groww.get_historical_candles(
                symbol=symbol,
                exchange="NSE",
                from_date="",
                to_date="",
                interval=interval,
            )

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Retrieved {len(candles)} candles in {duration:.2f}ms")

        return {"candles": candles}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "symbol": symbol})
        raise HTTPException(status_code=500, detail=f"Failed to fetch candles: {e}")


@router.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Get quote for a symbol."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Fetching quote for {symbol}")

        quote = groww.get_quote(symbol=symbol, exchange="NSE", segment="CASH")

        return quote
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "symbol": symbol})
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {e}")


@router.get("/ltp/{symbol}")
async def get_ltp(
    symbol: str,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Get last traded price for a symbol."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Fetching LTP for {symbol}")

        exchange_symbol = f"NSE_{symbol}"
        ltp_data = groww.get_ltp(exchange_trading_symbols=(exchange_symbol,), segment="CASH")

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
        log_error(logger, e, {"request_id": request_id, "symbol": symbol})
        raise HTTPException(status_code=500, detail=f"Failed to fetch LTP: {e}")


@router.get("/instruments/search")
async def search_instruments(
    q: str = Query(..., min_length=2, description="Search query"),
    segment: str = Query("CASH", description="CASH or FNO"),
    exchange: str = Query("NSE", description="Exchange filter"),
    limit: int = Query(20, le=50, description="Max results"),
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Search instruments by trading_symbol, name, or groww_symbol."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Searching instruments: q='{q}', segment={segment}, exchange={exchange}")

        from cache import market_cache

        df = market_cache.get_instruments(groww)

        if df.empty:
            return {"count": 0, "instruments": []}

        # Filter by segment and exchange
        mask = (df["segment"] == segment) & (df["exchange"] == exchange)
        df = df[mask]

        # CASH: only EQ series (drop bonds, NCDs)
        if segment == "CASH" and "series" in df.columns:
            df = df[df["series"].isin(["EQ", "BE", "SM", "ST"])]

        # Case-insensitive search on multiple fields
        q_lower = q.lower()
        search_mask = (
            df["trading_symbol"].str.lower().str.contains(q_lower, na=False)
            | df["name"].str.lower().str.contains(q_lower, na=False)
            | df["groww_symbol"].str.lower().str.contains(q_lower, na=False)
        )

        results = df[search_mask].head(limit)

        # Format results
        instruments = []
        for _, row in results.iterrows():
            inst = {
                "trading_symbol": str(row.get("trading_symbol", "")),
                "groww_symbol": str(row.get("groww_symbol", "")),
                "name": str(row.get("name", "")),
                "segment": str(row.get("segment", "")),
                "exchange": str(row.get("exchange", "")),
                "exchange_token": str(row.get("exchange_token", "")),
            }
            # Add FNO-specific fields
            if segment == "FNO":
                inst["expiry_date"] = str(row.get("expiry_date", "")) if pd.notna(row.get("expiry_date")) else ""
                inst["strike_price"] = float(row.get("strike_price", 0)) if pd.notna(row.get("strike_price")) else 0
                inst["instrument_type"] = str(row.get("instrument_type", ""))
                inst["underlying_symbol"] = str(row.get("underlying_symbol", ""))
            instruments.append(inst)

        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] Found {len(instruments)} instruments in {duration:.2f}ms")

        return {"count": len(instruments), "instruments": instruments}
    except Exception as e:
        log_error(logger, e, {"request_id": request_id, "query": q})
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.post("/order")
async def place_order(
    body: OrderRequest,
    groww: GrowwClientBase = Depends(get_groww_client_dep),
):
    """Place a trading order."""
    request_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{request_id}] Placing order: {body.trading_symbol} {body.transaction_type} {body.quantity}@{body.order_type}")

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
        log_error(logger, e, {"request_id": request_id, "symbol": body.trading_symbol})
        raise HTTPException(status_code=500, detail=f"Order failed: {e}")
