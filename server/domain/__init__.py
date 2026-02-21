"""Domain module exports."""

# Only export models if pydantic is available
try:
    from domain.models import (
        AlgoConfig,
        AlgoPerformance,
        AlgoSettings,
        AlgoSignal,
        AlgoStatus,
        BacktestRequest,
        BacktestResult,
        Candle,
        DailyPick,
        OrderRequest,
        OrderResponse,
        Position,
        Quote,
        Trade,
        TradeBase,
        TradeCreate,
        TradeFilter,
        TradeSummary,
        TradeUpdate,
    )

    __all__ = [
        "TradeBase",
        "TradeCreate",
        "TradeUpdate",
        "Trade",
        "TradeSummary",
        "TradeFilter",
        "AlgoSignal",
        "AlgoConfig",
        "AlgoSettings",
        "AlgoStatus",
        "AlgoPerformance",
        "Position",
        "Candle",
        "Quote",
        "DailyPick",
        "BacktestRequest",
        "BacktestResult",
        "OrderRequest",
        "OrderResponse",
    ]
except ImportError:
    # Pydantic not installed, models not available
    __all__ = []
