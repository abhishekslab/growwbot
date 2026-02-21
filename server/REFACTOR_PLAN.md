# Server Refactor Plan

## Executive Summary

This document outlines a comprehensive refactor of the `server/` codebase to improve maintainability, testability, and separation of concerns while ensuring zero breaking changes to the API.

**Current State:** ~3,800 lines of code with circular imports, mixed responsibilities, and no test infrastructure  
**Target State:** Clean layered architecture with dependency injection, comprehensive tests, and clear module boundaries

---

## 1. Current Issues Analysis

### 1.1 Critical Issues

| Issue | Impact | Location |
|-------|--------|----------|
| **Circular Imports** | `algo_engine.py` imports `get_groww_client` from `main.py`, while `main.py` imports `AlgoEngine` | `main.py:15-17`, `algo_engine.py:578-619` |
| **Global State** | Module-level globals make testing impossible | `main.py:44-48`, throughout |
| **God File** | `main.py` is 1368 lines handling auth, routes, token management | `main.py` |
| **No Dependency Injection** | Cannot mock external APIs for testing | Everywhere |
| **Mixed Concerns** | API routes, business logic, data access all mixed | Throughout |

### 1.2 Code Quality Issues

- **No type checking**: Using Python 3.9 comment-style type hints
- **No tests**: Zero test coverage
- **Inconsistent error handling**: Mix of patterns
- **Hardcoded constants**: Magic numbers scattered
- **Database migrations**: Manual try/except ALTER TABLE patterns
- **Configuration**: JSON file + env vars with no validation

---

## 2. Target Architecture

### 2.1 Package Structure


```
server/
├── app/                          # FastAPI application
│   ├── __init__.py
│   ├── main.py                   # Application factory (minimal)
│   ├── dependencies.py           # FastAPI dependency injection
│   ├── router.py                 # Route aggregation
│   └── api/                      # API routes only
│       ├── __init__.py
│       ├── holdings.py           # /api/holdings
│       ├── daily_picks.py        # /api/daily-picks/*
│       ├── trades.py             # /api/trades/*
│       ├── algos.py              # /api/algos/*
│       ├── backtest.py           # /api/backtest/*
│       ├── symbols.py            # /api/candles/*, /api/quote/*
│       ├── orders.py             # /api/order
│       ├── cache.py              # /api/cache/*
│       └── websocket.py          # /ws/ltp/*
│
├── core/                         # Core business logic (no FastAPI)
│   ├── __init__.py
│   ├── config.py                 # Pydantic settings
│   ├── auth.py                   # Token management (moved from main.py)
│   ├── exceptions.py             # Custom exceptions
│   └── logging.py                # Logging configuration
│
├── services/                     # Business logic layer
│   ├── __init__.py
│   ├── screener_service.py       # Daily picks logic
│   ├── algo_engine.py            # Algo trading engine
│   ├── position_monitor.py       # Position monitoring
│   ├── holdings_service.py       # Holdings enrichment
│   ├── trade_service.py          # Trade CRUD operations
│   ├── backtest_service.py       # Backtest runner
│   └── symbol_service.py         # Candle/quote fetching
│
├── repositories/                 # Data access layer
│   ├── __init__.py
│   ├── base.py                   # Abstract base repository
│   ├── trade_repository.py       # Trade DB operations
│   ├── algo_repository.py        # Algo settings/signals
│   ├── backtest_repository.py    # Backtest persistence
│   └── cache_repository.py       # In-memory cache
│
├── domain/                       # Domain models
│   ├── __init__.py
│   ├── models.py                 # Pydantic models
│   ├── enums.py                  # Status enums
│   └── events.py                 # Domain events
│
├── infrastructure/               # External integrations
│   ├── __init__.py
│   ├── groww_client.py           # Groww API wrapper
│   ├── database.py               # SQLite connection management
│   └── snapshot_store.py         # JSON file persistence
│
├── strategies/                   # Trading algorithms
│   ├── __init__.py
│   ├── base.py                   # BaseAlgorithm (from algo_base.py)
│   ├── momentum.py               # MomentumScalping
│   ├── mean_reversion.py         # MeanReversion
│   └── registry.py               # Strategy registration
│
├── utils/                        # Utilities
│   ├── __init__.py
│   ├── indicators.py             # Technical indicators
│   ├── fees.py                   # Fee calculations
│   └── time_utils.py             # IST time handling
│
└── tests/                        # Test suite (new)
    ├── __init__.py
    ├── conftest.py               # pytest fixtures
    ├── unit/                     # Unit tests
    │   ├── test_indicators.py
    │   ├── test_fees.py
    │   ├── test_algos.py
    │   └── test_services/
    ├── integration/              # Integration tests
    │   ├── test_api/
    │   ├── test_repositories/
    │   └── test_infrastructure/
    └── fixtures/                 # Test data
        ├── candles.json
        ├── trades.json
        └── quotes.json
```


### 2.2 Dependency Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer (app/api)                   │
│                   FastAPI routes only                        │
└────────────────────┬────────────────────────────────────────┘
                     │ depends on
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer (services)                   │
│              Business logic, orchestration                   │
│         (testable, no FastAPI deps, DI-aware)               │
└────────────────────┬────────────────────────────────────────┘
                     │ depends on
                     ▼
┌────────────────────┬────────────────────────────────────────┐
│         Repository Layer (repositories)      │  Infrastructure │
│         Data access abstraction              │  (infrastructure)│
│         (swappable: SQLite -> PostgreSQL)    │  External APIs  │
└────────────────────┴────────────────────────────────────────┘
```

---

## 3. Key Design Decisions

### 3.1 Dependency Injection Pattern

```python
# app/dependencies.py
from functools import lru_cache
from typing import Generator
from fastapi import Depends, Request

from core.config import Settings
from infrastructure.groww_client import GrowwClient
from infrastructure.database import get_db
from repositories.trade_repository import TradeRepository
from services.trade_service import TradeService

@lru_cache()
def get_settings() -> Settings:
    return Settings()

def get_groww_client(
    settings: Settings = Depends(get_settings)
) -> GrowwClient:
    return GrowwClient(
        api_key=settings.api_key,
        api_secret=settings.api_secret,
        token_path=settings.token_path
    )

def get_trade_repository() -> Generator[TradeRepository, None, None]:
    db = get_db()
    try:
        yield TradeRepository(db)
    finally:
        db.close()

def get_trade_service(
    repo: TradeRepository = Depends(get_trade_repository),
    groww: GrowwClient = Depends(get_groww_client)
) -> TradeService:
    return TradeRepository(repository=repo, groww_client=groww)
```

### 3.2 Repository Pattern

```python
# repositories/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional

T = TypeVar('T')
ID = TypeVar('ID')

class Repository(ABC, Generic[T, ID]):
    @abstractmethod
    def get(self, id: ID) -> Optional[T]: ...
    
    @abstractmethod
    def list(self, **filters) -> List[T]: ...
    
    @abstractmethod
    def create(self, entity: T) -> T: ...
    
    @abstractmethod
    def update(self, id: ID, data: dict) -> Optional[T]: ...
    
    @abstractmethod
    def delete(self, id: ID) -> bool: ...
```

### 3.3 Service Layer Pattern

```python
# services/trade_service.py
from typing import Optional
from domain.models import Trade, TradeCreate
from repositories.trade_repository import TradeRepository
from infrastructure.groww_client import GrowwClient

class TradeService:
    def __init__(
        self,
        repository: TradeRepository,
        groww_client: GrowwClient
    ):
        self._repo = repository
        self._groww = groww_client
    
    async def create_trade(self, data: TradeCreate) -> Trade:
        # Business logic here
        trade = self._repo.create(data)
        return trade
    
    async def close_trade(self, trade_id: int) -> Optional[Trade]:
        # Fetch LTP, calculate P&L, update status
        pass
```


---

## 4. Migration Strategy (7 Phases)

### Phase 1: Foundation (Week 1)
**Goal**: Create directory structure, move utilities

1. **Create new directory structure**
2. **Move utility functions** (no dependencies):
   - `indicators.py` → `utils/indicators.py`
   - Fee calculations from `position_monitor.py` → `utils/fees.py`
   - Time utilities → `utils/time_utils.py`
3. **Create configuration module** with Pydantic Settings
4. **Test**: Run `make lint` and existing API tests

### Phase 2: Domain Models (Week 1-2)
**Goal**: Define data contracts with Pydantic

1. **Create `domain/models.py`**
   - Trade, TradeCreate, TradeUpdate models
   - AlgoSignal model
   - ScreenerCandidate model
2. **Create `domain/enums.py`**
   - TradeStatus, OrderStatus, SignalType enums
3. **Test**: Validate models serialize correctly

### Phase 3: Repository Layer (Week 2)
**Goal**: Abstract database access

1. **Create `repositories/base.py`** - Abstract repository interface
2. **Implement `TradeRepository`** - Wrap `trades_db.py`
3. **Implement `AlgoRepository`** - Wrap algo settings/signals
4. **Implement `BacktestRepository`** - Wrap `backtest_db.py`
5. **Create `repositories/cache_repository.py`** - Wrap `cache.py`
6. **Test**: Repository unit tests with in-memory DB

### Phase 4: Infrastructure (Week 2-3)
**Goal**: External integrations with no circular deps

1. **Create `infrastructure/groww_client.py`**
   - Wrapper around GrowwAPI
   - Token management from `main.py`
   - No imports from app/ or services/
2. **Create `infrastructure/database.py`**
   - Connection pool management
   - Transaction handling
3. **Move `snapshot.py`** → `infrastructure/snapshot_store.py`
4. **Test**: Mock Groww client for isolated testing

### Phase 5: Service Layer (Week 3)
**Goal**: Extract business logic from routes

1. **Create `services/holdings_service.py`**
   - Enrichment logic from `/api/holdings`
   - Batch LTP fetching
2. **Create `services/trade_service.py`**
   - Trade CRUD operations
   - Fee calculations
3. **Create `services/screener_service.py`**
   - Daily picks logic from `screener.py`
4. **Create `services/backtest_service.py`**
   - Backtest runner logic
5. **Test**: Service unit tests with mocked repos

### Phase 6: Strategy Refactor (Week 3-4)
**Goal**: Clean algo structure, fix circular imports

1. **Move strategy files**:
   - `algo_base.py` → `strategies/base.py`
   - `algo_momentum.py` → `strategies/momentum.py`
   - `algo_mean_reversion.py` → `strategies/mean_reversion.py`
2. **Create `strategies/registry.py`**
   - Auto-discovery and registration
   - Factory for creating strategy instances
3. **Move `algo_engine.py`** → `services/algo_engine.py`
   - Use `infrastructure/groww_client.py` (not main.py)
   - Use repositories (not direct DB calls)
4. **Move `position_monitor.py`** → `services/position_monitor.py`
5. **Test**: Strategy backtests, algo engine integration tests

### Phase 7: API Refactor (Week 4)
**Goal**: Split `main.py` into route modules

1. **Create `app/dependencies.py`**
   - FastAPI dependency providers
2. **Create route modules**:
   - `app/api/holdings.py`
   - `app/api/daily_picks.py`
   - `app/api/trades.py`
   - `app/api/algos.py`
   - `app/api/backtest.py`
   - `app/api/symbols.py`
   - `app/api/orders.py`
   - `app/api/cache.py`
   - `app/api/websocket.py`
3. **Create `app/router.py`** - Aggregate all routes
4. **Update `app/main.py`** - Minimal factory
5. **Test**: Full API integration test suite

---

## 5. Backward Compatibility Plan

### 5.1 Zero Breaking Changes Guarantee
- All API routes keep exact same paths
- Request/response schemas remain identical
- Database schema unchanged
- Configuration format supported

### 5.2 Compatibility Strategy
```python
# During transition, support both patterns:

# OLD (current main.py)
def get_holdings():
    groww = get_groww_client()  # From main.py global
    # ... 80 lines

# NEW (services/holdings_service.py)
class HoldingsService:
    def __init__(self, groww_client: GrowwClient):
        self._groww = groww_client
    
    async def get_enriched_holdings(self):
        # Same logic, testable
        pass

# Route can proxy to both during migration
```

### 5.3 Database Compatibility
- Keep existing `trades.db` and `backtest_cache.db`
- Repositories wrap existing tables
- No migrations needed


---

## 6. Testing Strategy

### 6.1 Test Architecture

```
tests/
├── conftest.py                   # Shared fixtures
├── fixtures/                     # Test data files
│   ├── candles.json
│   ├── quotes.json
│   └── trades.json
├── unit/                         # Fast, isolated tests
│   ├── test_indicators.py
│   ├── test_fees.py
│   ├── test_algos.py
│   ├── test_time_utils.py
│   └── test_services/
│       ├── test_trade_service.py
│       ├── test_screener_service.py
│       └── test_algo_engine.py
├── integration/                  # API + DB tests
│   ├── test_api/
│   │   ├── test_holdings.py
│   │   ├── test_trades.py
│   │   ├── test_daily_picks.py
│   │   └── test_algos.py
│   └── test_repositories/
│       ├── test_trade_repository.py
│       └── test_algo_repository.py
└── e2e/                          # End-to-end (optional)
    └── test_trading_flow.py
```

### 6.2 pytest Configuration

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_groww_client():
    """Mock Groww API client"""
    client = MagicMock()
    client.get_ltp.return_value = {"NSE_RELIANCE": 2500.0}
    client.get_holdings_for_user.return_value = {"holdings": []}
    return client

@pytest.fixture
def sample_candles():
    """Sample 1-minute candle data"""
    return [
        {
            "time": 1609459200,
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 104.0,
            "volume": 10000
        },
        # ... more candles
    ]

@pytest.fixture
def test_db():
    """In-memory SQLite database for tests"""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Initialize schema...
    yield conn
    conn.close()

@pytest.fixture
def trade_repository(test_db):
    from repositories.trade_repository import TradeRepository
    return TradeRepository(test_db)
```

### 6.3 Example Unit Tests

```python
# tests/unit/test_indicators.py
import pytest
from utils.indicators import calculate_ema, calculate_rsi, calculate_atr

def test_ema_basic_calculation():
    closes = [100.0, 102.0, 101.0, 103.0, 105.0]
    ema = calculate_ema(closes, period=3)
    
    assert len(ema) == len(closes)
    assert all(isinstance(v, float) for v in ema if not math.isnan(v))
    # EMA should trend upward with rising prices
    assert ema[-1] > ema[0]

def test_rsi_overbought_signal():
    # Simulate 14 up days (RSI should be high)
    candles = [{"close": 100.0 + i} for i in range(20)]
    result = calculate_rsi(candles)
    
    assert result["zone"] == "OVERBOUGHT"
    assert result["current"] > 70

def test_rsi_oversold_signal():
    # Simulate 14 down days (RSI should be low)
    candles = [{"close": 100.0 - i} for i in range(20)]
    result = calculate_rsi(candles)
    
    assert result["zone"] == "OVERSOLD"
    assert result["current"] < 30
```

### 6.4 Example Service Tests

```python
# tests/unit/test_services/test_trade_service.py
import pytest
from unittest.mock import MagicMock
from services.trade_service import TradeService
from domain.models import TradeCreate

@pytest.fixture
def trade_service(mock_groww_client, trade_repository):
    return TradeService(
        repository=trade_repository,
        groww_client=mock_groww_client
    )

@pytest.mark.asyncio
async def test_create_trade(trade_service, trade_repository):
    # Arrange
    data = TradeCreate(
        symbol="RELIANCE",
        entry_price=2500.0,
        stop_loss=2450.0,
        target=2600.0,
        quantity=10,
        is_paper=True
    )
    
    # Act
    trade = await trade_service.create_trade(data)
    
    # Assert
    assert trade.symbol == "RELIANCE"
    assert trade.status == "OPEN"
    assert trade.is_paper == True
```

### 6.5 Example API Integration Tests

```python
# tests/integration/test_api/test_trades.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_trade_endpoint():
    response = client.post("/api/trades", json={
        "symbol": "RELIANCE",
        "entry_price": 2500.0,
        "stop_loss": 2450.0,
        "target": 2600.0,
        "quantity": 10,
        "is_paper": True
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "RELIANCE"
    assert "id" in data

def test_list_trades_endpoint():
    response = client.get("/api/trades")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

### 6.6 Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| `utils/indicators.py` | 95% | High |
| `utils/fees.py` | 95% | High |
| `strategies/*.py` | 90% | High |
| `services/*.py` | 85% | High |
| `repositories/*.py` | 80% | Medium |
| `app/api/*.py` | 80% | Medium |
| `infrastructure/*.py` | 70% | Low |


---

## 7. Implementation Checklist

### Phase 1: Foundation ✅
- [ ] Create directory structure
- [ ] Move `indicators.py` → `utils/indicators.py`
- [ ] Move fee calculations → `utils/fees.py`
- [ ] Create `utils/time_utils.py` for IST handling
- [ ] Create `core/config.py` with Pydantic Settings
- [ ] Create `core/exceptions.py` for custom exceptions
- [ ] Update `requirements.txt` with pydantic-settings
- [ ] Run `make lint` - should pass

### Phase 2: Domain Layer ✅
- [ ] Create `domain/models.py`
  - [ ] Trade, TradeCreate, TradeUpdate
  - [ ] AlgoSignal
  - [ ] ScreenerCandidate
  - [ ] Holdings, Quote
- [ ] Create `domain/enums.py`
  - [ ] TradeStatus
  - [ ] OrderStatus
  - [ ] SignalType
  - [ ] MarketStatus
- [ ] Write unit tests for models

### Phase 3: Repository Layer ✅
- [ ] Create `repositories/base.py` (Abstract Repository)
- [ ] Create `repositories/trade_repository.py`
- [ ] Create `repositories/algo_repository.py`
- [ ] Create `repositories/backtest_repository.py`
- [ ] Create `repositories/cache_repository.py`
- [ ] Write repository tests with in-memory DB

### Phase 4: Infrastructure ✅
- [ ] Create `infrastructure/groww_client.py`
  - [ ] Extract from `main.py` auth logic
  - [ ] Token persistence
  - [ ] Rate limiting
- [ ] Create `infrastructure/database.py`
  - [ ] Connection management
  - [ ] Transaction context manager
- [ ] Move `snapshot.py` → `infrastructure/snapshot_store.py`
- [ ] Write infrastructure tests with mocks

### Phase 5: Service Layer ✅
- [ ] Create `services/holdings_service.py`
- [ ] Create `services/trade_service.py`
- [ ] Create `services/screener_service.py` (from `screener.py`)
- [ ] Create `services/backtest_service.py` (from `backtest_engine.py`)
- [ ] Create `services/symbol_service.py` (from `symbol.py`)
- [ ] Write service tests with mocked repos

### Phase 6: Strategy Refactor ✅
- [ ] Move `algo_base.py` → `strategies/base.py`
- [ ] Move `algo_momentum.py` → `strategies/momentum.py`
- [ ] Move `algo_mean_reversion.py` → `strategies/mean_reversion.py`
- [ ] Create `strategies/registry.py`
- [ ] Move `algo_engine.py` → `services/algo_engine.py` (fix circular imports)
- [ ] Move `position_monitor.py` → `services/position_monitor.py`
- [ ] Write strategy tests
- [ ] Write algo engine tests

### Phase 7: API Refactor ✅
- [ ] Create `app/dependencies.py`
- [ ] Create `app/api/holdings.py`
- [ ] Create `app/api/daily_picks.py`
- [ ] Create `app/api/trades.py`
- [ ] Create `app/api/algos.py`
- [ ] Create `app/api/backtest.py`
- [ ] Create `app/api/symbols.py`
- [ ] Create `app/api/orders.py`
- [ ] Create `app/api/cache.py`
- [ ] Create `app/api/websocket.py`
- [ ] Create `app/router.py`
- [ ] Refactor `app/main.py` to minimal factory
- [ ] Write API integration tests

### Phase 8: Testing & Polish ✅
- [ ] Setup pytest configuration (`pytest.ini` or `pyproject.toml`)
- [ ] Achieve 80%+ unit test coverage
- [ ] Add GitHub Actions CI pipeline
- [ ] Performance benchmarks (before/after)
- [ ] Documentation updates
- [ ] Migration guide for team

---

## 8. File Migration Map

| Old Path | New Path | Phase | Notes |
|----------|----------|-------|-------|
| `indicators.py` | `utils/indicators.py` | 1 | Direct move |
| `position_monitor.py` (fees) | `utils/fees.py` | 1 | Extract fee functions |
| `snapshot.py` | `infrastructure/snapshot_store.py` | 4 | Direct move |
| `trades_db.py` | `repositories/trade_repository.py` | 3 | Wrap with Repository class |
| `backtest_db.py` | `repositories/backtest_repository.py` | 3 | Wrap with Repository class |
| `cache.py` | `repositories/cache_repository.py` | 3 | Add Repository interface |
| `algo_base.py` | `strategies/base.py` | 6 | Strategy interface |
| `algo_momentum.py` | `strategies/momentum.py` | 6 | Direct move |
| `algo_mean_reversion.py` | `strategies/mean_reversion.py` | 6 | Direct move |
| `algo_engine.py` | `services/algo_engine.py` | 6 | Fix circular imports |
| `position_monitor.py` | `services/position_monitor.py` | 6 | Remove fee functions |
| `screener.py` | `services/screener_service.py` | 5 | Service wrapper |
| `backtest_engine.py` | `services/backtest_service.py` | 5 | Split engine/service |
| `symbol.py` | `services/symbol_service.py` | 5 | Service wrapper |
| `main.py` (routes) | `app/api/*.py` | 7 | Split into modules |
| `main.py` (auth) | `core/auth.py` + `infrastructure/groww_client.py` | 4 | Extract |
| `main.py` (factory) | `app/main.py` | 7 | Minimal factory |

---

## 9. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking API changes | Low | High | Keep old routes as proxies during transition; full integration test suite |
| Circular import resolution | Medium | Medium | Careful dependency analysis; interface extraction |
| Performance regression | Low | Medium | Benchmark before/after; cache layer unchanged |
| Extended timeline | Medium | Low | Phased approach; rollback at each phase; parallel old/new code |
| Team learning curve | Medium | Low | Documentation; pair programming; code review |
| Database migration issues | Low | High | No schema changes; repositories wrap existing tables |

---

## 10. Success Criteria

- [ ] **All API endpoints respond identically** - verified by integration tests
- [ ] **No circular imports** - verified by `python -c "import app.main"`
- [ ] **80%+ test coverage** - verified by `pytest --cov`
- [ ] **All existing features work** - manual QA of UI
- [ ] **Performance maintained** - benchmark comparison
- [ ] **Lint passes** - `make lint` clean
- [ ] **Team approval** - code review sign-off

---

## Summary

This refactor transforms a monolithic 3,800-line codebase with circular imports into a clean, testable architecture with:

- **7 distinct layers**: API, Services, Repositories, Domain, Infrastructure, Strategies, Utils
- **Zero breaking changes**: Full backward compatibility
- **Comprehensive testing**: Unit, integration, and fixture-based tests
- **Dependency injection**: Easy mocking and testing
- **Clear boundaries**: Each module has a single responsibility

**Estimated Timeline**: 4-5 weeks  
**Estimated Effort**: 2-3 developer-weeks  
**Risk Level**: Low-Medium (gradual migration with fallbacks)

