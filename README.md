# GrowwBot

A real-time stock screening and trading dashboard for the Indian equity market (NSE). Built with a Python FastAPI backend wrapping the Groww Trade API and a Next.js 16 frontend.

## Features

- **Daily Picks Scanner** — Multi-stage screener pipeline with progressive SSE streaming, volume enrichment, and news correlation
- **Live Price Tracking** — Tiered LTP updates via SSE (high-conviction stocks every 3s, others every 15s)
- **Portfolio Dashboard** — Holdings view with batch LTP enrichment and candlestick charts
- **Trade Calculator** — Risk-based position sizing with full Indian exchange fee breakdown (STT, stamp duty, GST, etc.)
- **Trade Ledger** — SQLite-backed trade journal with P&L tracking and analytics
- **Order Execution** — Place NSE CASH orders directly from the dashboard

## Architecture

```
┌─────────────────────┐       ┌─────────────────────┐
│   Next.js 16 App    │──────▶│   FastAPI Backend    │
│   (client/)         │ REST  │   (server/)          │
│                     │  SSE  │                      │
│   localhost:3000    │  WS   │   localhost:8000     │
└─────────────────────┘       └──────────┬───────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   Groww Trade API    │
                              └─────────────────────┘
```

## Prerequisites

- **Python 3.9+** and `pip3`
- **Node.js 20+** and `npm`
- **Groww Trade API** credentials (`API_KEY` and `API_SECRET`)

## Quick Start

### Option 1: Docker (recommended)

```bash
cp server/.env.example server/.env
# Edit server/.env with your Groww API credentials

docker compose up --build
```

Frontend: http://localhost:3000 | Backend: http://localhost:8000

### Option 2: Manual Setup

```bash
# Install all dependencies
make install

# Configure credentials
cp server/.env.example server/.env
# Edit server/.env with your Groww API credentials

# Start both servers (requires two terminals)
make dev
```

Or start each server individually:

```bash
# Terminal 1: Backend
cd server && python3 -m uvicorn main:app --reload

# Terminal 2: Frontend
cd client && npm run dev
```

## Makefile Targets

| Target          | Description                              |
|-----------------|------------------------------------------|
| `make install`  | Install all dependencies (server + client + git hooks) |
| `make dev`      | Start both servers (backend + frontend)  |
| `make lint`     | Run ruff (backend) + eslint + prettier (frontend) |
| `make build`    | Production build of the frontend         |
| `make clean`    | Remove build artifacts and caches        |
| `make docker-up`| Start services via Docker Compose        |
| `make docker-down` | Stop Docker Compose services          |

## Environment Variables

Create `server/.env` from the example file:

| Variable      | Description                | Required |
|---------------|----------------------------|----------|
| `API_KEY`     | Groww Trade API key        | Yes      |
| `API_SECRET`  | Groww Trade API secret     | Yes      |

The frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

## Project Structure

```
growwbot/
├── server/                  # Python FastAPI backend
│   ├── main.py              # All API routes
│   ├── screener.py          # Multi-stage stock screener pipeline
│   ├── cache.py             # In-memory cache with TTL expiration
│   ├── snapshot.py          # Atomic JSON persistence
│   ├── trades_db.py         # SQLite trade ledger
│   ├── symbol.py            # Candle/quote/LTP helpers
│   └── requirements.txt     # Python dependencies
├── client/                  # Next.js 16 frontend
│   ├── app/                 # App router pages
│   ├── components/          # React components
│   ├── lib/                 # Utilities (trade calculator, etc.)
│   └── package.json         # Node dependencies
├── docker-compose.yml       # One-command dev setup
├── Makefile                 # Task runner
└── CLAUDE.md                # AI assistant context
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style guidelines, and the PR process.

## License

[Apache License 2.0](LICENSE)
