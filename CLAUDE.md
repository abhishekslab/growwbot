# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
make install          # Install all deps (server + client + git hooks)
make dev              # Start both servers (backend :8000 + frontend :3000)
make lint             # Run ruff (backend) + eslint + prettier (frontend)
make build            # Production build (runs TypeScript checks)
make clean            # Remove build artifacts and caches
docker compose up --build   # One-command dev setup (alternative to make dev)
```

### Running services individually

```bash
# Backend
cd server && pip3 install -r requirements.txt
python3 -m uvicorn main:app --reload          # http://localhost:8000

# Frontend
cd client && npm install
npm run dev                                    # http://localhost:3000
```

### Linting & formatting individually

```bash
python3 -m ruff check server/                 # Python linter (config: server/pyproject.toml)
cd client && npx eslint .                      # TypeScript linter (config: client/eslint.config.mjs)
cd client && npx prettier --check .            # Formatting check
cd client && npx prettier --write .            # Auto-format
```

Both servers must run simultaneously. The frontend fetches from the backend at `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`). No test framework is configured. Pre-commit hooks (Husky + lint-staged) run eslint + prettier on staged client files.

## Architecture

Two-service app: a Python FastAPI backend wrapping the Groww Trade API, and a Next.js 16 (React 19) client-side dashboard. All frontend components use `"use client"` (no SSR). No global state manager — components use local `useState` with `useCallback`/`useRef` for SSE/WebSocket refs and `localStorage`-backed settings via `useTradeSettings` hook.

### Backend (`server/`)

**`main.py`** — FastAPI app with ~25 routes + 1 WebSocket. Authentication is cached globally with lazy refresh + rate-limit backoff. CORS is configured for `http://localhost:3000`.

**Key API endpoint groups:**
- **Daily Picks** — The core feature. Three endpoints form a pipeline:
  - `GET /api/daily-picks/snapshot` — Returns last persisted scan (instant page load)
  - `GET /api/daily-picks/stream` — SSE streaming scan with progressive updates, saves snapshot on completion
  - `GET /api/daily-picks/live-ltp` — SSE continuous LTP updates with tiered refresh (high-conviction every 3s, others every 15s)
- **Portfolio** — `GET /api/holdings` (batch LTP enrichment)
- **Symbol** — `GET /api/candles/{symbol}` (supports 3min via 1min aggregation), `GET /api/quote/{symbol}`, `GET /api/ltp/{symbol}`, `WS /ws/ltp/{symbol}`
- **Trade Ledger** — Full CRUD at `/api/trades`, plus `GET /api/trades/summary`, `/api/trades/analytics`, `/api/trades/realized-pnl`, `/api/trades/active`, `POST /api/trades/{id}/close`, `POST /api/trades/buy`
- **Algo Engine** — `GET /api/algos` (status), `POST /api/algos/{id}/start|stop`, `PATCH /api/algos/{id}/settings`, `GET /api/algos/performance`, `GET /api/algos/{id}/signals`
- **Order Execution** — `POST /api/order` (NSE CASH)
- **Cache** — `GET /api/cache/status`, `POST /api/cache/warmup`, `POST /api/cache/clear`

**`screener.py`** — Multi-stage stock screener pipeline: (1) Batch OHLC scan → (2) Volume enrichment (parallel ThreadPoolExecutor) → (3) Criteria tagging (Gainer, Volume Leader, High Conviction) → (4) News enrichment (Google News RSS, 48h). Streaming version yields SSE events: `batch` → `stage_complete` → `complete`.

**`algo_engine.py`** — Background daemon running a 60-second evaluation cycle. Loads `algo_config.json` for parameters. Each cycle: reads Daily Picks snapshot, fetches 1min candles (2min cache per symbol, max 8 fresh API calls/cycle), runs each registered algo's `evaluate()`, creates trades on signal. Signal buffer: `deque(maxlen=200)` ring buffer for UI visibility. DB-persisted enabled state per algo.

**`algo_base.py` / `algo_momentum.py` / `algo_mean_reversion.py`** — Strategy pattern. `BaseAlgorithm` defines `evaluate(symbol, candles, ltp, candidate_info) → AlgoSignal | None`. Momentum: EMA 9/21 crossover + RSI 40-65 + volume spike + above VWAP, target 2.5x ATR. Mean Reversion: price below VWAP by >1 ATR + RSI <35 + volume >2x, target reverts to VWAP.

**`position_monitor.py`** — Background daemon polling every 5s (exponential backoff on failures). Fetches all OPEN trades, batch LTP (50/batch), auto-exits on SL/target breach via MARKET SELL. Contains Python port of fee calculation logic.

**`cache.py`** — In-memory cache with TTL-based expiration (thread-safe via `threading.RLock`). TTLs: instruments 24h, OHLC 5min, historical 24h, news 6h. LTP values have no TTL but are age-tracked.

**`trades_db.py`** — SQLite (WAL mode). Tables: `trades` (status: OPEN→WON/LOST/CLOSED, order_status: PLACED/REJECTED/FILLED/SIMULATED), `algo_signals`, `algo_settings`. Migrations are idempotent (CREATE IF NOT EXISTS + try/except ALTER TABLE).

**`indicators.py`** — Technical indicators: EMA, RSI (Wilder's), ATR, VWAP (session-anchored at 9:15 IST), volume analysis.

**`snapshot.py`** — Atomic JSON persistence using `tempfile.mkstemp` + `os.replace`.

**`symbol.py`** — Candle fetching (resolves groww_symbol from trading_symbol), quote enrichment, exchange token resolution for WebSocket feeds.

### Frontend (`client/`)

**`app/page.tsx`** — Daily Picks page with a **three-phase lifecycle**:
1. **Snapshot** — Fetch `/api/daily-picks/snapshot` on mount for instant table render
2. **Scanning** — SSE stream from `/api/daily-picks/stream` replaces snapshot data progressively; runs `analyzeCandles()` on top candidates (parallel batches of 5)
3. **Live** — SSE stream from `/api/daily-picks/live-ltp` patches LTP values continuously, rows rearrange, flash animations on price changes

**Other pages:** `/portfolio` (holdings + charts), `/symbol/[symbol]` (candlestick chart + order panel + WebSocket LTP), `/trade/[symbol]` (position sizer + fee calculator), `/trades` (trade ledger), `/algos` (algo status + signal feed + performance).

**`lib/tradeCalculator.ts`** — Risk-based position sizing (capital × risk% ÷ risk-per-share) with Indian exchange fee calculations (brokerage, STT, exchange txn, SEBI, stamp duty, GST).

**`lib/candleAnalysis.ts`** — Client-side technical analysis: EMA 9/21, RSI 14, VWAP, ATR, volume ratio, support/resistance. Returns verdict: BUY / WAIT / AVOID with score.

**`hooks/useTradeSettings.ts`** — `localStorage`-backed settings (capital, riskPercent, tradeType, rrRatio, maxPositions, paperMode, autoCompound). Also exposes `useCompoundedCapital()` which fetches realized P&L from backend.

## Key Patterns & Constraints

### Python 3.9 Requirement
`pip` is not on PATH — always use `pip3`. Prefer `python3 -m uvicorn` over bare `uvicorn`. **Cannot use** `dict | None` or `list[dict]` syntax (Python 3.10+) — must use `Optional[dict]` and `List[dict]` from `typing`. Ruff is configured to ignore UP006/UP007/UP035 for this reason.

### Fee Parity
`position_monitor.py` (Python) and `lib/tradeCalculator.ts` (TypeScript) both implement Indian exchange fee formulas (brokerage, STT, stamp duty, GST, etc.). These **must stay in sync** — changing one without the other breaks P&L calculations and algo exit logic.

### IST Time Handling
Trading hours are hardcoded in IST (UTC+5:30). VWAP session anchors at 9:15 IST (3:45 UTC). Algo trading windows: momentum 09:30-15:00, mean reversion 10:00-14:30. The offset is `timedelta(hours=5, minutes=30)` — not a timezone library.

### Recharts TypeScript
Use `PieLabelRenderProps` type import for Pie `label` prop. For Tooltip `formatter`, omit the parameter type annotation and use `Number(value)`.

### Frontend Conventions
- **Currency**: All monetary values use `₹` with `toLocaleString("en-IN")`.
- **Dark mode**: Every component must include Tailwind `dark:` variants.
- **SSE**: `EventSource` with `onmessage`/`onerror`, auto-reconnect after 5s. Always clean up refs on unmount.
- **WebSocket with polling fallback**: Symbol page tries WebSocket for live LTP, falls back to REST polling on disconnect.
- **Prettier**: 100 char width, semicolons, double quotes, trailing commas, tailwindcss plugin for class ordering.

### Backend Conventions
- **Daemon threads**: `PositionMonitor` and `AlgoEngine` are background daemons accessing shared SQLite DB from threads.
- **Batch limits**: Groww API enforces 50-symbol batches — hardcoded in multiple places (`cache.py`, `position_monitor.py`, `main.py`).
- **Symbol resolution**: Different Groww APIs return different symbol formats — always use the instrument cache wrapper to resolve.
- **Ruff config**: line-length 150, select E/F/W/I/UP/B/SIM with multiple ignores for 3.9 compat and existing patterns.

### Environment
Backend credentials go in `server/.env` (see `.env.example`: `API_KEY`, `API_SECRET`). Frontend API URL is configurable via `NEXT_PUBLIC_API_URL`.
