# Contributing to GrowwBot

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Development Setup

### Prerequisites

- Python 3.9+ with `pip3`
- Node.js 20+ with `npm`
- Groww Trade API credentials

### Getting Started

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/growwbot.git
cd growwbot

# Install all dependencies (server + client + git hooks)
make install

# Set up credentials
cp server/.env.example server/.env
# Edit server/.env with your API keys

# Start development servers
make dev
```

### Running Linters

```bash
make lint
```

This runs:
- **ruff** on `server/` (Python linting)
- **eslint** on `client/` (TypeScript linting)
- **prettier** on `client/` (formatting check)

Pre-commit hooks automatically run eslint and prettier on staged files.

## Code Style

### Backend (Python)

- **Formatter/Linter:** [Ruff](https://docs.astral.sh/ruff/) (configured in `server/pyproject.toml`)
- **Target:** Python 3.9 — use `Optional[X]` and `List[X]` from `typing`, not `X | None` or `list[X]`
- **Line length:** 150 characters
- **Imports:** sorted by ruff (isort rules)
- Use `pip3` (not `pip`) and `python3 -m uvicorn` (not bare `uvicorn`)

### Frontend (TypeScript/React)

- **Formatter:** [Prettier](https://prettier.io/) (configured in `client/.prettierrc.json`)
- **Linter:** [ESLint](https://eslint.org/) with Next.js config
- **Style:** Semicolons, double quotes, trailing commas
- All components use `"use client"` (no SSR)
- Currency values: `toLocaleString("en-IN")` with `₹` prefix
- Every component must include Tailwind `dark:` variants

### Commit Messages

Use clear, descriptive commit messages:

```
Add portfolio chart with candlestick view
Fix capital overallocation in position sizer
Update screener pipeline to batch volume enrichment
```

- Start with a verb (Add, Fix, Update, Remove, Refactor)
- Keep the subject line under 72 characters
- Use the body for "why", not "what"

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`
2. **Make your changes** with clear, focused commits
3. **Run the linters:** `make lint`
4. **Build the frontend:** `make build` (runs TypeScript checks)
5. **Test manually** — no automated test framework is configured yet
6. **Open a PR** against `main` with a clear description

### PR Checklist

- [ ] `make lint` passes (ruff + eslint + prettier)
- [ ] `make build` succeeds (TypeScript compiles)
- [ ] Dark mode works for any UI changes
- [ ] No `.env` files or secrets included

## Project Architecture

See [CLAUDE.md](CLAUDE.md) for a detailed architecture overview including API endpoints, data flow, and key patterns.

## Questions?

Open an issue if you have questions or run into problems. We're happy to help!
