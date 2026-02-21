"""
Domain models for the GrowwBot application.

Pydantic models for type-safe data handling across the application.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TradeBase(BaseModel):
    """Base trade model with common fields."""

    symbol: str
    trade_type: str = Field(default="INTRADAY", pattern="^(INTRADAY|DELIVERY)$")
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    target: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    capital_used: float = Field(..., gt=0)
    risk_amount: float = Field(..., gt=0)
    fees_entry: float = Field(default=0, ge=0)
    fees_exit_target: float = Field(default=0, ge=0)
    fees_exit_sl: float = Field(default=0, ge=0)
    notes: str = ""
    is_paper: bool = Field(default=True)
    entry_snapshot: Optional[str] = None


class TradeCreate(TradeBase):
    """Model for creating a new trade."""

    entry_date: Optional[str] = None


class TradeUpdate(BaseModel):
    """Model for updating an existing trade."""

    status: Optional[str] = Field(None, pattern="^(OPEN|CLOSED|WON|LOST|FAILED)$")
    exit_price: Optional[float] = Field(None, ge=0)
    actual_pnl: Optional[float] = None
    actual_fees: Optional[float] = Field(None, ge=0)
    exit_date: Optional[str] = None
    notes: Optional[str] = None
    stop_loss: Optional[float] = Field(None, gt=0)
    target: Optional[float] = Field(None, gt=0)
    exit_trigger: Optional[str] = Field(None, pattern="^(SL|TARGET|MANUAL)$")


class Trade(TradeBase):
    """Full trade model as stored in database."""

    id: int
    status: str = Field(default="OPEN", pattern="^(OPEN|CLOSED|WON|LOST|FAILED)$")
    exit_price: Optional[float] = None
    actual_pnl: Optional[float] = None
    actual_fees: Optional[float] = None
    entry_date: str
    exit_date: Optional[str] = None
    created_at: str
    updated_at: str
    order_status: Optional[str] = Field(None, pattern="^(PLACED|REJECTED|FILLED|SIMULATED)$")
    groww_order_id: Optional[str] = None
    exit_trigger: Optional[str] = Field(None, pattern="^(SL|TARGET|MANUAL)$")
    algo_id: Optional[str] = None
    algo_version: Optional[str] = None

    class Config:
        orm_mode = True


class TradeSummary(BaseModel):
    """Summary statistics for trades."""

    total_trades: int
    open_trades: int
    won_trades: int
    lost_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_profit: float
    max_loss: float
    avg_profit: float
    avg_loss: float
    profit_factor: float


class TradeFilter(BaseModel):
    """Filter criteria for listing trades."""

    status: Optional[str] = None
    symbol: Optional[str] = None
    is_paper: Optional[bool] = None
    algo_id: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class AlgoSignal(BaseModel):
    """Algorithm signal/decision record."""

    id: int
    timestamp: str
    algo_id: str
    symbol: str
    decision: str = Field(..., pattern="^(ENTRY|SKIP|EXIT|ERROR)$")
    reason: str
    confidence: float = Field(..., ge=0, le=100)
    metadata: Optional[str] = None


class AlgoConfig(BaseModel):
    """Algorithm configuration."""

    capital: float = Field(default=100000, gt=0)
    risk_percent: float = Field(default=1, gt=0, le=100)
    max_positions_per_algo: int = Field(default=3, gt=0)
    max_total_positions: int = Field(default=6, gt=0)
    trading_start_ist: str = Field(default="09:30")
    trading_end_ist: str = Field(default="15:00")
    force_close_ist: str = Field(default="15:15")
    max_trade_duration_minutes: int = Field(default=15, gt=0)


class AlgoSettings(BaseModel):
    """Algorithm runtime settings."""

    enabled: bool = True
    config: AlgoConfig


class AlgoStatus(BaseModel):
    """Algorithm runtime status."""

    id: str
    name: str
    enabled: bool
    running: bool
    last_run: Optional[str] = None
    positions_count: int
    today_signals: int
    today_trades: int


class AlgoPerformance(BaseModel):
    """Algorithm performance metrics."""

    algo_id: str
    total_signals: int
    entry_signals: int
    skipped_signals: int
    trades_created: int
    win_rate: float
    avg_profit: float
    total_pnl: float


class Position(BaseModel):
    """Open position summary."""

    trade_id: int
    symbol: str
    entry_price: float
    current_price: float
    quantity: int
    unrealized_pnl: float
    stop_loss: float
    target: float
    risk_percent: float


class Candle(BaseModel):
    """OHLCV candle data."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class Quote(BaseModel):
    """Market quote data."""

    symbol: str
    ltp: float
    change: float
    change_percent: float
    volume: int
    day_high: float
    day_low: float
    day_open: float
    prev_close: float


class DailyPick(BaseModel):
    """Daily stock pick from screener."""

    symbol: str
    price: float
    change_percent: float
    volume_ratio: float
    tags: list
    news_count: int
    conviction: str = Field(..., pattern="^(HIGH|MEDIUM|LOW)$")
    ltp: Optional[float] = None


class BacktestRequest(BaseModel):
    """Backtest run request."""

    symbol: str
    start_date: str
    end_date: str
    algo_id: str
    initial_capital: float = Field(default=100000, gt=0)


class BacktestResult(BaseModel):
    """Backtest run result."""

    id: str
    symbol: str
    start_date: str
    end_date: str
    algo_id: str
    initial_capital: float
    final_capital: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    created_at: str


class OrderRequest(BaseModel):
    """Order placement request."""

    symbol: str
    transaction_type: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., gt=0)
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT|SL|SL-M)$")
    price: float = Field(default=0, ge=0)
    trigger_price: float = Field(default=0, ge=0)
    product: str = Field(default="CNC", pattern="^(CNC|MIS)$")
    validity: str = Field(default="DAY", pattern="^(DAY|IOC)$")


class OrderResponse(BaseModel):
    """Order placement response."""

    success: bool
    order_id: Optional[str] = None
    message: str
    status: str


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
