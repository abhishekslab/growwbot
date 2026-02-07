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
npm run lint      # ESLint
```

Both servers must run simultaneously. The frontend fetches from the backend at `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

## Architecture

Two-service app: a Python FastAPI backend that wraps the Groww Trade API, and a Next.js client-side dashboard.

**Backend** (`server/main.py`): Single `GET /api/holdings` endpoint. Authenticates via `GrowwAPI.get_access_token()`, fetches user holdings, enriches each with live LTP prices, computes P&L metrics, and returns a JSON payload with `holdings[]` and `summary{}`. CORS is configured for the frontend origin.

**Frontend** (`client/`): Next.js 16 with App Router. All components are client components (`"use client"`). The page (`app/page.tsx`) fetches data on mount and passes it down to four components: `PortfolioSummary` (stat cards), `HoldingsTable` (sortable table), `AllocationChart` (Recharts pie), `PnLChart` (Recharts bar).

## Key Patterns

- **Recharts TypeScript**: Use `PieLabelRenderProps` type import for Pie `label` prop. For Tooltip `formatter`, omit the parameter type annotation and use `Number(value)` to handle `number | undefined`.
- **Currency formatting**: All monetary values use `₹` with `toLocaleString("en-IN")`.
- **Dark mode**: Every component includes Tailwind `dark:` variants.
- **Environment**: Backend credentials go in `server/.env` (see `.env.example`). Frontend API URL is configurable via `NEXT_PUBLIC_API_URL`.

## Python Environment Note

Python 3.9 is installed via CommandLineTools. `pip` is not on PATH — always use `pip3`. The `uvicorn` binary installs to `~/Library/Python/3.9/bin/`, so prefer `python3 -m uvicorn` over bare `uvicorn`.
