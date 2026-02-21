"""Core module exports."""

from core.exceptions import (
    AlgorithmError,
    ApiError,
    AuthenticationError,
    BacktestError,
    CacheError,
    DatabaseError,
    GrowwBotException,
    MarketHoursError,
    OrderError,
    PositionMonitorError,
    RateLimitError,
    SymbolNotFoundError,
    TradeError,
    ValidationError,
)
from core.logging_config import (
    get_logger,
    log_error,
    log_request,
    log_response,
    setup_logging,
)

# Config imports may fail if pydantic is not installed
__all__ = [
    "GrowwBotException",
    "AuthenticationError",
    "ApiError",
    "SymbolNotFoundError",
    "TradeError",
    "OrderError",
    "ValidationError",
    "DatabaseError",
    "CacheError",
    "AlgorithmError",
    "BacktestError",
    "PositionMonitorError",
    "RateLimitError",
    "MarketHoursError",
    "get_logger",
    "log_request",
    "log_response",
    "log_error",
    "setup_logging",
]

try:
    from core.config import get_api_credentials, get_database_path, get_settings, get_token_file, Settings

    __all__.extend(
        [
            "Settings",
            "get_settings",
            "get_api_credentials",
            "get_database_path",
            "get_token_file",
        ]
    )
except ImportError:
    pass  # Pydantic not installed
