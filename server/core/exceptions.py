"""
Custom exceptions for the GrowwBot application.

Provides domain-specific exceptions for better error handling and API responses.
"""


class GrowwBotException(Exception):
    """Base exception for all GrowwBot errors."""

    def __init__(self, message="An error occurred", status_code=500):
        # type: (str, int) -> None
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthenticationError(GrowwBotException):
    """Raised when authentication with Groww API fails."""

    def __init__(self, message="Authentication failed"):
        # type: (str) -> None
        super().__init__(message, status_code=401)


class ApiError(GrowwBotException):
    """Raised when Groww API returns an error."""

    def __init__(self, message="API request failed", status_code=502):
        # type: (str, int) -> None
        super().__init__(message, status_code)


class SymbolNotFoundError(GrowwBotException):
    """Raised when a trading symbol cannot be resolved."""

    def __init__(self, symbol=""):
        # type: (str) -> None
        msg = f"Symbol not found: {symbol}" if symbol else "Symbol not found"
        super().__init__(msg, status_code=404)
        self.symbol = symbol


class TradeError(GrowwBotException):
    """Raised when a trade operation fails."""

    def __init__(self, message="Trade operation failed"):
        # type: (str) -> None
        super().__init__(message, status_code=400)


class OrderError(GrowwBotException):
    """Raised when order placement fails."""

    def __init__(self, message="Order placement failed", order_id=None):
        # type: (str, Optional[str]) -> None
        super().__init__(message, status_code=400)
        self.order_id = order_id


class ValidationError(GrowwBotException):
    """Raised when input validation fails."""

    def __init__(self, message="Validation failed", field=None):
        # type: (str, Optional[str]) -> None
        super().__init__(message, status_code=422)
        self.field = field


class DatabaseError(GrowwBotException):
    """Raised when database operation fails."""

    def __init__(self, message="Database operation failed"):
        # type: (str) -> None
        super().__init__(message, status_code=500)


class CacheError(GrowwBotException):
    """Raised when cache operation fails."""

    def __init__(self, message="Cache operation failed"):
        # type: (str) -> None
        super().__init__(message, status_code=500)


class AlgorithmError(GrowwBotException):
    """Raised when algorithm execution fails."""

    def __init__(self, message="Algorithm execution failed", algo_name=None):
        # type: (str, Optional[str]) -> None
        super().__init__(message, status_code=500)
        self.algo_name = algo_name


class BacktestError(GrowwBotException):
    """Raised when backtest operation fails."""

    def __init__(self, message="Backtest operation failed"):
        # type: (str) -> None
        super().__init__(message, status_code=500)


class PositionMonitorError(GrowwBotException):
    """Raised when position monitoring fails."""

    def __init__(self, message="Position monitor error"):
        # type: (str) -> None
        super().__init__(message, status_code=500)


class RateLimitError(GrowwBotException):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message="Rate limit exceeded", retry_after=None):
        # type: (str, Optional[int]) -> None
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class MarketHoursError(GrowwBotException):
    """Raised when operation is attempted outside market hours."""

    def __init__(self, message="Operation not allowed outside market hours"):
        # type: (str) -> None
        super().__init__(message, status_code=403)


class HoldingsError(GrowwBotException):
    """Raised when holdings operation fails."""

    def __init__(self, message="Holdings operation failed"):
        # type: (str) -> None
        super().__init__(message, status_code=500)
