"""Main API router combining all route modules."""

from fastapi import APIRouter, WebSocket

from app.api import algos, backtest, cache, daily_picks, holdings, system, trades, symbols, websocket

api_router = APIRouter()

api_router.include_router(trades.router)
api_router.include_router(algos.router)
api_router.include_router(system.router)
api_router.include_router(holdings.router)
api_router.include_router(symbols.router)
api_router.include_router(cache.router)
api_router.include_router(backtest.router)
api_router.include_router(daily_picks.router)

websocket_router = websocket.router

__all__ = ["api_router", "websocket_router"]
