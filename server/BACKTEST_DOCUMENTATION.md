# Backtest System Documentation

A comprehensive guide to the GrowwBot backtesting system, covering architecture, data flow, and implementation details.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [File Structure](#file-structure)
4. [API Endpoints](#api-endpoints)
5. [Complete Execution Flow](#complete-execution-flow)
6. [Candle Caching System](#candle-caching-system)
7. [Database Persistence](#database-persistence)
8. [Strategy System](#strategy-system)
9. [Technical Indicators](#technical-indicators)
10. [Metrics Computation](#metrics-computation)
11. [SSE Event Protocol](#sse-event-protocol)
12. [Error Handling](#error-handling)
13. [Configuration](#configuration)

---

## Overview

The backtest system enables historical simulation of trading strategies using actual market data. It:

- Fetches historical candle data from Groww API (with caching)
- Simulates strategy execution on each candle
- Manages virtual positions with stop-loss and target
- Computes performance metrics
- Persists results to SQLite database
- Streams progress via Server-Sent Events (SSE)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT                                        │
│  POST /api/backtest/run {algo_id, symbol, dates, params...}        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    app/api/backtest.py                              │
│  - BacktestRunRequest (Pydantic model)                             │
│  - run_backtest_endpoint()                                         │
│  - _backtest_event_generator()                                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│  strategies/registry.py          │  │  infrastructure/groww_client.py │
│  - StrategyRegistry.initialize()│  │  - get_historical_candles()    │
│  - StrategyRegistry.get()       │  │  (Maps to Groww API params)    │
└─────────────────────────────────┘  └─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      backtest_engine.py                             │
│  run_backtest() ─ Main execution engine                            │
│  ├─ cache_get_candles() → backtest_cache.py                       │
│  ├─ algo.evaluate() → strategies/*.py                             │
│  ├─ compute_exit_pnl() → utils/fees.py                            │
│  ├─ _compute_metrics() → Performance metrics                      │
│  └─ save_backtest_run() → backtest_db.py                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

### Core Files

| File | Purpose |
|------|---------|
| `server/backtest_engine.py` | Main execution engine, iterate candles, evaluate strategy, compute metrics |
| `server/backtest_cache.py` | SQLite caching for historical candle data |
| `server/backtest_db.py` | SQLite persistence for backtest run results |
| `server/app/api/backtest.py` | FastAPI endpoints |

### Supporting Files

| File | Purpose |
|------|---------|
| `server/strategies/base.py` | `BaseAlgorithm` class and `AlgoSignal` dataclass |
| `server/strategies/momentum.py` | MomentumScalping strategy implementation |
| `server/strategies/mean_reversion.py` | MeanReversion strategy implementation |
| `server/strategies/registry.py` | Strategy registration and discovery |
| `server/utils/fees.py` | Fee calculation and P&L computation |
| `server/utils/indicators.py` | Technical indicators (EMA, RSI, VWAP, ATR) |
| `server/infrastructure/groww_client.py` | Groww API wrapper |

### Database Files

| File | Purpose |
|------|---------|
| `server/backtest_cache.db` | Combined SQLite database (candle cache + run results) |

---

## API Endpoints

All endpoints are prefixed with `/api/backtest`

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/run` | Run a backtest (returns SSE stream) |
| GET | `/history` | List past backtest runs |
| GET | `/{run_id}` | Get specific backtest results |
| DELETE | `/{run_id}` | Delete a backtest run |

### Cache Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cache/status` | Get cache statistics |
| POST | `/cache/warmup` | Pre-fetch candle data |
| POST | `/cache/clear` | Clear candle cache |

### FNO Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/expiries` | Get FNO expiry dates |
| GET | `/contracts` | Get FNO contracts |

### Request Model

```python
# server/app/api/backtest.py - BacktestRunRequest
class BacktestRunRequest(BaseModel):
    algo_id: str                    # Strategy ID (e.g., "momentum_scalp", "mean_reversion")
    groww_symbol: str               # Trading symbol (e.g., "RELIANCE", "TATAELXSI")
    exchange: str = "NSE"         # Exchange (NSE/BSE)
    segment: str = "CASH"          # Segment (CASH/FNO)
    start_date: str                # Start date (YYYY-MM-DD)
    end_date: str                  # End date (YYYY-MM-DD)
    candle_interval: str = "5minute" # Candle interval (1minute, 5minute, etc.)
    initial_capital: float = 100000 # Starting capital in ₹
    risk_percent: float = 1.0      # Risk per trade as percentage
    max_positions: int = 1        # Maximum concurrent positions
```

### Example Request

```bash
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "algo_id": "momentum_scalp",
    "groww_symbol": "RELIANCE",
    "exchange": "NSE",
    "segment": "CASH",
    "start_date": "2025-02-10",
    "end_date": "2025-02-14",
    "candle_interval": "5minute",
    "initial_capital": 100000,
    "risk_percent": 1,
    "max_positions": 1
  }'
```

---

## Complete Execution Flow

### Step-by-Step Process

```
1. Client Request
   │
   ▼
2. run_backtest_endpoint(BacktestRunRequest, groww)
   │
   ├─► StrategyRegistry.initialize()     # Register strategies if not done
   ├─► StrategyRegistry.get(algo_id)    # Get strategy instance
   │
   ▼
3. _backtest_event_generator(request, groww)
   │
   ▼
4. run_backtest() Generator
   │
   ├─► 4a. cache_get_candles()
   │    │
   │    ├─► Parse date range → calendar days
   │    ├─► Query candle_cache table for each day
   │    ├─► Identify missing date ranges
   │    ├─► For each gap:
   │    │    ├─► Chunk by INTERVAL_MAX_DAYS
   │    │    ├─► groww.get_historical_candles()
   │    │    │    (Maps to: exchange, segment, groww_symbol, 
   │    │    │            start_time, end_time, candle_interval)
   │    │    └─► Store each day in cache
   │    └─► Merge cached + fetched, sort by time
   │
   ├─► 4b. Main Loop (for each candle)
   │    │
   │    ├─► Check existing position
   │    │    ├─► Has SL been hit? → Exit at stop_loss
   │    │    ├─► Has target been hit? → Exit at target
   │    │    └─► Has max duration exceeded? → Force exit
   │    │
   │    ├─► Compute unrealized P&L
   │    │
   │    ├─► Update equity_curve
   │    │
   │    ├─► If no open position AND i >= 30:
   │    │    │
   │    │    ├─► algo.set_runtime_params(equity, risk_percent)
   │    │    │
   │    │    ├─► Build candidate_info:
   │    │    │    {
   │    │    │      symbol, open, high, low, close,
   │    │    │      volume, open_interest
   │    │    │    }
   │    │    │
   │    │    ├─► signal = algo.evaluate()
   │    │    │    │
   │    │    │    ├─► Calculate indicators (EMA, RSI, VWAP, ATR)
   │    │    │    ├─► Apply entry filters
   │    │    │    ├─► Compute position size
   │    │    │    └─► Return AlgoSignal or None
   │    │    │
   │    │    └─► If BUY signal:
   │    │         └─► Open position
   │    │
   │    ├─► Yield progress event (every 5%)
   │    │
   │    └─► Yield trade event (on exit)
   │
   ├─► 4c. Compute metrics
   │    │   _compute_metrics(initial_capital, trades, equity_curve)
   │    │
   │    └─► save_backtest_run() → Get run_id
   │
   └─► Yield complete event with run_id
```

---

## Candle Caching System

### Purpose

Avoid redundant API calls by caching historical candle data in SQLite.

### Database Schema

```sql
-- server/backtest_cache.py
CREATE TABLE IF NOT EXISTS candle_cache (
    groww_symbol TEXT NOT NULL,
    segment TEXT NOT NULL,
    interval TEXT NOT NULL,
    date TEXT NOT NULL,           -- Calendar date (YYYY-MM-DD)
    candles_json TEXT NOT NULL,   -- JSON array of candles
    fetched_at TEXT NOT NULL,    -- ISO timestamp
    PRIMARY KEY (groww_symbol, segment, interval, date)
);
```

### Cache Functions

| Function | File:Line | Purpose |
|----------|-----------|---------|
| `get_candles()` | `backtest_cache.py:142` | Main entry point - returns cached/fetched candles |
| `get_cache_stats()` | `backtest_cache.py:280` | Returns cache statistics |
| `clear_cache()` | `backtest_cache.py:290` | Purge cache entries |

### Interval Limits

The Groww API has limits on how much historical data can be fetched per request. The system chunks requests accordingly:

```python
# server/backtest_cache.py - INTERVAL_MAX_DAYS
{
    "1minute": 30,    # Max 30 days of 1-minute candles
    "5minute": 30,    # Max 30 days of 5-minute candles
    "10minute": 90,
    "15minute": 90,
    "30minute": 90,
    "1hour": 180,
    "4hours": 180,
    "1day": 180,
    "1week": 180,
    "1month": 180
}
```

### Cache Flow

```
get_candles(groww, groww_symbol, segment, interval, start_date, end_date, exchange)
    │
    ├─► Convert start/end to calendar days
    │
    ├─► Query candle_cache for each day
    │    SELECT * FROM candle_cache 
    │    WHERE groww_symbol=? AND segment=? AND interval=? AND date=?
    │
    ├─► Identify missing dates
    │
    ├─► For each missing date range:
    │    ├─► Chunk by INTERVAL_MAX_DAYS
    │    ├─► groww.get_historical_candles(
    │    │    exchange=exchange,
    │    │    segment=segment,
    │    │    groww_symbol=groww_symbol,
    │    │    start_time=start_str,   # "YYYY-MM-DD HH:MM:SS"
    │    │    end_time=end_str,
    │    │    candle_interval=interval
    │    │   )
    │    │
    │    └─► Insert each day:
    │        INSERT OR REPLACE INTO candle_cache 
    │        (groww_symbol, segment, interval, date, candles_json, fetched_at)
    │
    └─► Merge all candles, sort by time, return
```

---

## Database Persistence

### Purpose

Store completed backtest runs for later retrieval and comparison.

### Database Schema

```sql
-- server/backtest_db.py
CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    algo_id TEXT NOT NULL,
    groww_symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    segment TEXT NOT NULL,
    interval TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    config_json TEXT,      -- JSON: {initial_capital, risk_percent, max_positions}
    metrics_json TEXT,     -- JSON: Performance metrics
    trades_json TEXT,      -- JSON: [Trade array]
    equity_curve_json TEXT,-- JSON: [{time, equity}, ...]
    created_at TEXT NOT NULL
);

CREATE INDEX idx_backtest_runs_algo_id ON backtest_runs(algo_id);
CREATE INDEX idx_backtest_runs_created_at ON backtest_runs(created_at);
```

### Persistence Functions

| Function | File:Line | Purpose |
|----------|-----------|---------|
| `save_backtest_run()` | `backtest_db.py:62` | Save complete run results, returns run_id |
| `list_backtest_runs()` | `backtest_db.py:97` | List past runs with summary |
| `get_backtest_run()` | `backtest_db.py:130` | Get full results for specific run |
| `delete_backtest_run()` | `backtest_db.py:155` | Delete a run |

### Persistence Flow

```
On backtest completion (complete event):
    │
    ▼
save_backtest_run(
    algo_id="momentum_scalp",
    groww_symbol="RELIANCE",
    exchange="NSE",
    segment="CASH",
    interval="5minute",
    start_date="2025-02-10",
    end_date="2025-02-14",
    config={initial_capital: 100000, risk_percent: 1, max_positions: 1},
    metrics={total_return_pct: 0.25, net_pnl: 246.01, win_rate: 100, ...},
    trades=[{entry_price: 1217.9, exit_price: 1221.92, pnl: 246.01, ...}],
    equity_curve=[{time: 1739159100, equity: 100000}, ...]
)
    │
    ├─► JSON serialize config, metrics, trades, equity_curve
    │
    ├─► INSERT INTO backtest_runs (...)
    │
    └─► RETURN run_id (included in final SSE event)
```

---

## Strategy System

### Strategy Interface

```python
# server/strategies/base.py - BaseAlgorithm
class BaseAlgorithm(ABC):
    ALGO_ID: str = "base"
    
    @abstractmethod
    def evaluate(self, symbol: str, candles: List[dict], ltp: float, candidate_info: dict) -> Optional[AlgoSignal]:
        """Evaluate and return trading signal or None."""
        pass
    
    def set_runtime_params(self, effective_capital: float, risk_percent: float):
        """Called by engine with per-cycle capital and risk params."""
        pass
    
    def should_skip_symbol(self, symbol: str, candidate_info: dict, open_positions: List[dict]) -> bool:
        """Check if symbol already has position."""
        pass
```

### AlgoSignal Dataclass

```python
# server/strategies/base.py - AlgoSignal
@dataclass
class AlgoSignal:
    algo_id: str           # Strategy identifier
    symbol: str            # Trading symbol
    action: str            # "BUY" or "HOLD"
    entry_price: float     # Proposed entry price
    stop_loss: float       # Stop loss price
    target: float          # Target price
    quantity: int          # Position size
    confidence: float      # 0.0 to 1.0
    reason: str            # Human-readable reason
    fee_breakeven: float   # Min price move to cover fees
    expected_profit: float # Expected profit in ₹
```

### Available Strategies

#### MomentumScalping (`server/strategies/momentum.py`)

Entry criteria:
- EMA 9 > EMA 21 (bullish crossover)
- RSI in range 40-65
- Volume > 1.5x average
- Price above VWAP

Exit targets:
- Target: Entry + 1.5x ATR
- Stop Loss: Entry - 1.0x ATR

```python
# server/strategies/momentum.py - MomentumScalping.evaluate()
def evaluate(self, symbol: str, candles: List[dict], ltp: float, candidate_info: dict) -> Optional[AlgoSignal]:
    # 1. Validate minimum candles (need 30+)
    # 2. Calculate indicators: EMA 9, EMA 21, RSI, VWAP, ATR
    # 3. Check entry filters:
    #    - EMA9 > EMA21 (recent bullish)
    #    - RSI in [40, 65]
    #    - Volume > 1.5x average
    #    - Close > VWAP
    # 4. Compute position:
    #    - Entry = current close
    #    - Target = Entry + 1.5 * ATR
    #    - SL = Entry - 1.0 * ATR
    #    - Quantity = risk-based sizing
    # 5. Return AlgoSignal or None
```

#### MeanReversion (`server/strategies/mean_reversion.py`)

Entry criteria:
- Price below VWAP by > 1 ATR
- RSI < 35 (oversold)
- Volume > 2x average

Exit targets:
- Target: VWAP (mean reversion)
- Stop Loss: Entry - 1.5x ATR

### Strategy Registry

```python
# server/strategies/registry.py - StrategyRegistry
class StrategyRegistry:
    _strategies: Dict[str, Type[BaseAlgorithm]] = {}
    _initialized: bool = False
    
    @classmethod
    def register(cls, algo_id: str, strategy_class: Type[BaseAlgorithm]):
        """Register a strategy class."""
        cls._strategies[algo_id] = strategy_class
    
    @classmethod
    def get(cls, algo_id: str, config: dict) -> Optional[BaseAlgorithm]:
        """Get strategy instance with optional config."""
        if not cls._initialized:
            cls.initialize()
        
        strategy_class = cls._strategies.get(algo_id)
        if strategy_class:
            return strategy_class.clone_with_config(config)
        return None
    
    @classmethod
    def initialize(cls):
        """Register built-in strategies."""
        cls.register("momentum_scalp", MomentumScalping)
        cls.register("mean_reversion", MeanReversion)
        cls._initialized = True
```

---

## Technical Indicators

Calculated in `server/utils/indicators.py`:

| Indicator | Function | Description |
|-----------|----------|-------------|
| EMA | `calculate_ema(candles, period)` | Exponential Moving Average |
| RSI | `calculate_rsi(candles, period=14)` | Relative Strength Index |
| VWAP | `calculate_vwap(candles)` | Volume Weighted Average Price (session-anchored at 9:15 IST) |
| ATR | `calculate_atr(candles, period=14)` | Average True Range |
| Volume | `analyze_volume(candles)` | Volume analysis with average |

### Indicator Calculations

```python
# EMA - Exponential Moving Average
# Formula: EMA_today = (Close_today * k) + (EMA_yesterday * (1-k))
# where k = 2 / (period + 1)

# RSI - Relative Strength Index
# Formula: RSI = 100 - (100 / (1 + RS))
# where RS = Average Gain / Average Loss (Wilder's smoothing)

# VWAP - Volume Weighted Average Price
# Formula: Σ(Price * Volume) / Σ(Volume)
# Anchored at market open (9:15 IST for equity)

# ATR - Average True Range
# Formula: Average of True Range over period
# TR = max(H-L, |H-PC|, |L-PC|)
```

---

## Metrics Computation

Computed in `server/backtest_engine.py` via `_compute_metrics()`:

### Output Fields

```python
{
    "initial_capital": float,      # Starting capital
    "final_equity": float,         # Ending equity
    "total_return_pct": float,    # (final - initial) / initial * 100
    "total_fees": float,           # Sum of all trading fees
    "net_pnl": float,              # total_pnl - total_fees
    "trade_count": int,            # Total closed trades
    "wins": int,                   # Profitable trades
    "losses": int,                 # Losing trades
    "win_rate_pct": float,         # wins / trade_count * 100
    "profit_factor": float,         # gross_profit / abs(gross_loss)
    "expectancy": float,           # (win_rate * avg_win) + (loss_rate * avg_loss)
    "max_drawdown": float,         # Largest peak-to-trough decline (₹)
    "max_drawdown_pct": float,     # As percentage
    "sharpe_ratio": float,         # (mean_return / std_return) * sqrt(252)
    "sortino_ratio": float,         # Like sharpe but only downside deviation
    "avg_win": float,              # Average winning trade
    "avg_loss": float,             # Average losing trade
    "best_trade": float,           # Best single trade
    "worst_trade": float,          # Worst single trade
    "avg_duration_seconds": float  # Average holding time
}
```

### Calculation Formulas

```
Win Rate = Wins / Total Trades * 100

Profit Factor = Gross Profit / |Gross Loss|
              = Sum(winners) / abs(sum(losers))

Expectancy = (Win Rate% * Avg Win) + (Loss Rate% * Avg Loss)

Max Drawdown = max(peak - trough) over entire equity curve

Sharpe Ratio = (Mean Daily Return / Std Dev of Daily Returns) * sqrt(252)
             = Risk-adjusted return metric

Sortino Ratio = Like Sharpe but uses downside deviation only
```

---

## SSE Event Protocol

The backtest streams results using Server-Sent Events (SSE).

### Event Types

#### Progress Event
```json
{
  "event_type": "progress",
  "percent": 45.0,
  "current_date": "2025-02-12 06:45",
  "bars_processed": 201,
  "total_bars": 404
}
```

#### Trade Event (on exit)
```json
{
  "event_type": "trade",
  "trade": {
    "entry_price": 1217.9,
    "exit_price": 1221.92,
    "quantity": 82,
    "entry_time": 1739352900,
    "exit_time": 1739418600,
    "pnl": 246.01,
    "fees": 83.63,
    "exit_trigger": "TARGET",
    "reason": "EMA 9/21 crossover, RSI 62.1, Vol 2.1x, Above VWAP"
  }
}
```

#### Complete Event (final)
```json
{
  "event_type": "complete",
  "metrics": {...},
  "trades": [...],
  "equity_curve": [...],
  "signal_analysis": {
    "EMA Bearish — no uptrend": 205,
    "Price Below VWAP": 5,
    "No Recent Crossover": 138,
    "Volume Below Average": 13
  },
  "run_id": 11
}
```

#### Error Event
```json
{
  "event_type": "complete",
  "error": "No candle data for the given range. Check that...",
  "metrics": {},
  "trades": [],
  "equity_curve": []
}
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Strategy not found` | Invalid `algo_id` | Use valid strategy: `momentum_scalp` or `mean_reversion` |
| `No candle data` | Wrong symbol or date range | Use correct symbol format (e.g., `RELIANCE` not `NSE-RELIANCE`), use past dates |
| `GrowwAPI.get_historical_candles() got unexpected keyword argument` | Parameter mismatch | Fixed in `infrastructure/groww_client.py` |

### Error Logging

```python
# server/backtest_engine.py - Strategy evaluation errors
try:
    signal = algo.evaluate(groww_symbol, candles[:i+1], candle["close"], candidate_info)
except Exception as e:
    logger.error(f"Strategy evaluation error at bar {i} for {groww_symbol}: {e}")
    signal = None
```

---

## Configuration

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algo_id` | string | required | Strategy to use |
| `groww_symbol` | string | required | Trading symbol |
| `exchange` | string | "NSE" | Exchange |
| `segment` | string | "CASH" | Segment (CASH/FNO) |
| `start_date` | string | required | Start date (YYYY-MM-DD) |
| `end_date` | string | required | End date (YYYY-MM-DD) |
| `candle_interval` | string | "5minute" | Candle interval |
| `initial_capital` | float | 100000 | Starting capital (₹) |
| `risk_percent` | float | 1.0 | Risk per trade (%) |
| `max_positions` | int | 1 | Max concurrent positions |

### Valid Candle Intervals

```python
VALID_INTERVALS = [
    "1minute", "5minute", "10minute", "15minute", "30minute",
    "1hour", "4hours",
    "1day", "1week", "1month"
]
```

---

## Troubleshooting

### Frontend Shows "Loading..." Indefinitely

Check:
1. Server logs for errors: `tail -f logs/growwbot.log`
2. Network tab for SSE connection status
3. Browser console for JavaScript errors

### No Trades Generated

Possible reasons:
1. Symbol has insufficient volatility
2. Date range has no trading days
3. Strategy criteria not met
4. Entry filters too strict

### Cache Issues

Clear cache:
```bash
curl -X POST http://localhost:8000/api/backtest/cache/clear
```

Check cache status:
```bash
curl http://localhost:8000/api/backtest/cache/status
```

---

## Testing

### Run a Test Backtest

```bash
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "algo_id": "momentum_scalp",
    "groww_symbol": "RELIANCE",
    "start_date": "2025-02-10",
    "end_date": "2025-02-14",
    "candle_interval": "5minute"
  }'
```

### Check History

```bash
curl http://localhost:8000/api/backtest/history
```

### Get Specific Run

```bash
curl http://localhost:8000/api/backtest/11
```

---

## Version History

| Date | Change |
|------|--------|
| 2026-02-21 | Added StrategyRegistry initialization in API endpoint |
| 2026-02-21 | Fixed GrowwClient parameter mapping |
| 2026-02-21 | Added database persistence with run_id |
| 2026-02-21 | Fixed signal_analysis NameError |
| 2026-02-21 | Added error logging for strategy evaluation |
