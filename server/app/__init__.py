"""API module exports."""

from app.dependencies import get_algo_service, get_trade_service

# API routes require FastAPI - make optional
try:
    from app.api import algos, system, trades
    from app.legacy_routes import router as legacy_router
    from app.router import api_router

    __all__ = [
        "api_router",
        "legacy_router",
        "trades",
        "algos",
        "system",
        "get_trade_service",
        "get_algo_service",
    ]
except ImportError:
    # FastAPI not installed
    __all__ = [
        "get_trade_service",
        "get_algo_service",
    ]
