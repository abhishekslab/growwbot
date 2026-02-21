"""
GrowwBot API - Refactored Main Application

This is the new main application entry point with:
- Clean architecture using services and repositories
- Comprehensive request/response logging
- Both old and new API routes for backward compatibility
- Structured error handling
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Initialize logging first
from core.logging_config import get_logger, setup_logging

# Setup logging before anything else
logger = setup_logging(level="INFO", log_to_file=True, log_to_console=True)

# Load environment variables
load_dotenv()

# Import new architecture components
from app.router import api_router as new_api_router
from core.exceptions import GrowwBotException
from services.algo_service import AlgoService
from services.trade_service import TradeService

# Import legacy components (for backward compatibility)
from algo_engine import AlgoEngine
from algo_mean_reversion import MeanReversion
from algo_momentum import MomentumScalping
from cache import MarketCache
from position_monitor import PositionMonitor
from trades_db import init_db

# Legacy daemon instances
market_cache = MarketCache()
monitor = PositionMonitor()
algo_engine = AlgoEngine()
algo_engine.register_algo(MomentumScalping(algo_engine._config))
algo_engine.register_algo(MeanReversion(algo_engine._config))

# New service instances (using DI)
trade_service: Optional[TradeService] = None
algo_service: Optional[AlgoService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting GrowwBot API Server")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")

    # Initialize new services
    global trade_service, algo_service
    from repositories import TradeRepository, AlgoRepository

    trade_service = TradeService(TradeRepository())
    algo_service = AlgoService(AlgoRepository())
    logger.info("Services initialized")

    # Start legacy daemons
    logger.info("Starting position monitor...")
    monitor.start()
    logger.info("Position monitor started")

    logger.info("Starting algo engine...")
    algo_engine.start()
    logger.info("Algo engine started")

    logger.info("✅ Server startup complete")

    yield

    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down GrowwBot API Server")
    logger.info("=" * 60)

    logger.info("Stopping algo engine...")
    algo_engine.stop()
    logger.info("Algo engine stopped")

    logger.info("Stopping position monitor...")
    monitor.stop()
    logger.info("Position monitor stopped")

    logger.info("✅ Server shutdown complete")


# Create FastAPI application
app = FastAPI(title="GrowwBot API", description="Trading automation API with algorithmic strategies", version="2.0.0", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """
    Middleware for request/response logging.

    Logs all incoming requests and outgoing responses with timing
    and request IDs for traceability.
    """
    # Generate request ID
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    # Log request
    start_time = time.time()
    logger.info(
        f"[{request_id}] → Request {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client": request.client.host if request.client else "unknown",
            "event": "request_start",
        },
    )

    # Process request
    try:
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        log_level = "info" if response.status_code < 400 else "warning"
        log_method = getattr(logger, log_level)

        log_method(
            f"[{request_id}] ← Response {request.method} {request.url.path} {response.status_code} in {duration_ms:.2f}ms",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "event": "request_complete",
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] ✗ Error {request.method} {request.url.path}: {str(e)}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
                "error_type": type(e).__name__,
                "event": "request_error",
            },
            exc_info=True,
        )
        raise


# Custom exception handler for our exceptions
@app.exception_handler(GrowwBotException)
async def growwbot_exception_handler(request: Request, exc: GrowwBotException):
    """Handle custom GrowwBot exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        f"[{request_id}] Exception: {exc.message}",
        extra={
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "error_message": exc.message,
            "status_code": exc.status_code,
            "path": request.url.path,
            "event": "exception",
        },
    )

    return JSONResponse(
        status_code=exc.status_code, content={"success": False, "error": exc.message, "error_type": type(exc).__name__, "request_id": request_id}
    )


# General exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        f"[{request_id}] Unhandled Exception: {str(exc)}",
        extra={
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": request.url.path,
            "event": "unhandled_exception",
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500, content={"success": False, "error": "Internal server error", "error_type": type(exc).__name__, "request_id": request_id}
    )


# Include new API routes
app.include_router(new_api_router)
logger.info("New API routes mounted")

# Include websocket routes
from app.router import websocket_router

app.include_router(websocket_router)
logger.info("WebSocket routes mounted")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {"name": "GrowwBot API", "version": "2.0.0", "status": "running", "docs": "/docs", "endpoints": {"api": "/api/*", "websocket": "/ws/*"}}


@app.get("/api/info")
async def api_info():
    """Get API information and available endpoints."""
    return {
        "name": "GrowwBot API",
        "version": "2.0.0",
        "description": "Trading automation API",
        "routes": {"trades": "/api/trades", "algos": "/api/algos", "system": "/api/system", "legacy": "/api/v1"},
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
