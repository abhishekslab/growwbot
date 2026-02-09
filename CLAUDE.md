# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### Backend (server/)
```bash
cd server
pip3 install -r requirements.txt           # pip is not on PATH; use pip3
python3 -m uvicorn main:app --reload       # runs on http://localhost:8000
```

### Frontend (client/)
```bash
cd client
npm install
npm run dev       # http://localhost:3000
npm run build     # production build (runs TypeScript checks)
npm run lint      # ESLint (v9 flat config)
```

Both servers must run simultaneously. The frontend fetches from the backend at `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`). No test framework is configured.

## Architecture

Two-service app: a Python FastAPI backend wrapping the Groww Trade API, and a Next.js 16 client-side dashboard. All frontend components use `"use client"` (no SSR).

### Backend (`server/`)

**`main.py`** — FastAPI app with all routes. Authentication is cached globally with a 5-minute TTL (`_cached_client`). CORS is configured for `http://localhost:3000`.

**Key API endpoint groups:**
- **Daily Picks** — The core feature. Three endpoints form a pipeline:
  - `GET /api/daily-picks/snapshot` — Returns last persisted scan (instant page load)
  - `GET /api/daily-picks/stream` — SSE streaming scan with progressive updates, saves snapshot on completion
  - `GET /api/daily-picks/live-ltp` — SSE continuous LTP updates with tiered refresh (high-conviction every 3s, others every 15s)
- **Portfolio** — `GET /api/holdings` (batch LTP enrichment)
- **Symbol** — `GET /api/candles/{symbol}`, `GET /api/quote/{symbol}`, `GET /api/ltp/{symbol}`, `WS /ws/ltp/{symbol}`
- **Trade Ledger** — Full CRUD at `/api/trades` + `GET /api/trades/summary`
- **Order Execution** — `POST /api/order` (NSE CASH)
- **Cache** — `GET /api/cache/status`, `POST /api/cache/warmup`, `POST /api/cache/clear`

**`screener.py`** — Multi-stage stock screener pipeline:
1. Batch OHLC scan (all NSE CASH equities, top 100 movers + top 30 F&O)
2. Volume enrichment (quote API, parallel with ThreadPoolExecutor)
3. Criteria tagging: Gainer (turnover ≥ ₹50L + volume ≥ 100k), Volume Leader (≥ 500k), High Conviction (gainer + F&O eligible)
4. News enrichment (Google News RSS, 48h window)

Both synchronous (`run_daily_picks`) and streaming (`run_daily_picks_streaming`) versions exist. The streaming version yields SSE events: `batch` → `stage_complete` → `complete`.

**`cache.py`** — In-memory cache with TTL-based expiration (thread-safe via `threading.RLock`). TTLs: instruments 24h, OHLC 5min, historical 24h, news 6h. Also stores live LTP values (no TTL, age-tracked). Background warmup pre-fetches all instruments + OHLC batches.

**`snapshot.py`** — Atomic JSON persistence using `tempfile.mkstemp` + `os.replace`. Stores last scan result to `daily_picks_snapshot.json` for instant page loads.

**`trades_db.py`** — SQLite trade ledger (WAL mode). Tracks positions with entry/exit prices, fees, P&L. Status: OPEN → WON/LOST/CLOSED.

**`symbol.py`** — Helpers for candle fetching (resolves groww_symbol from trading_symbol), quote enrichment, and exchange token resolution for WebSocket feeds.

### Frontend (`client/`)

**`app/page.tsx`** — Daily Picks page with a **three-phase lifecycle**:
1. **Snapshot** — Fetch `/api/daily-picks/snapshot` on mount for instant table render
2. **Scanning** — SSE stream from `/api/daily-picks/stream` replaces snapshot data progressively
3. **Live** — SSE stream from `/api/daily-picks/live-ltp` patches LTP values continuously, rows rearrange, flash animations on price changes

**Other pages:** `/portfolio` (holdings + charts), `/symbol/[symbol]` (candlestick chart + order panel + WebSocket LTP), `/trade/[symbol]` (position sizer + fee calculator), `/trades` (trade ledger).

**`lib/tradeCalculator.ts`** — Risk-based position sizing (capital × risk% ÷ risk-per-share) with Indian exchange fee calculations (brokerage, STT, exchange txn, SEBI, stamp duty, GST).

## Key Patterns

- **Recharts TypeScript**: Use `PieLabelRenderProps` type import for Pie `label` prop. For Tooltip `formatter`, omit the parameter type annotation and use `Number(value)`.
- **Currency formatting**: All monetary values use `₹` with `toLocaleString("en-IN")`.
- **Dark mode**: Every component includes Tailwind `dark:` variants.
- **SSE handling**: `EventSource` with `onmessage`/`onerror`, auto-reconnect after 5s on disconnect. Refs cleaned up on unmount.
- **WebSocket with polling fallback**: Symbol page uses WebSocket for live LTP, falls back to REST polling on disconnect.
- **Environment**: Backend credentials go in `server/.env` (see `.env.example`). Frontend API URL is configurable via `NEXT_PUBLIC_API_URL`.

## Python Environment Note

Python 3.9 is installed via CommandLineTools. `pip` is not on PATH — always use `pip3`. The `uvicorn` binary installs to `~/Library/Python/3.9/bin/`, so prefer `python3 -m uvicorn` over bare `uvicorn`. Cannot use `dict | None` or `list[dict]` syntax (Python 3.10+) — must use `Optional[dict]` and `List[dict]` from `typing`.
