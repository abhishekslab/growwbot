"""
SQLite persistence layer for trade ledger.

Uses Python's built-in sqlite3 — no extra dependencies.
Database file: server/trades.db (auto-created on first run).
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List

DB_PATH = os.path.join(os.path.dirname(__file__), "trades.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            trade_type TEXT NOT NULL DEFAULT 'INTRADAY',
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            target REAL NOT NULL,
            quantity INTEGER NOT NULL,
            capital_used REAL NOT NULL,
            risk_amount REAL NOT NULL,
            fees_entry REAL NOT NULL DEFAULT 0,
            fees_exit_target REAL NOT NULL DEFAULT 0,
            fees_exit_sl REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'OPEN',
            exit_price REAL,
            actual_pnl REAL,
            actual_fees REAL,
            entry_date TEXT NOT NULL,
            exit_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def create_trade(data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    cursor = conn.execute(
        """
        INSERT INTO trades (
            symbol, trade_type, entry_price, stop_loss, target, quantity,
            capital_used, risk_amount, fees_entry, fees_exit_target, fees_exit_sl,
            status, entry_date, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
        """,
        (
            data["symbol"],
            data.get("trade_type", "INTRADAY"),
            data["entry_price"],
            data["stop_loss"],
            data["target"],
            data["quantity"],
            data["capital_used"],
            data["risk_amount"],
            data.get("fees_entry", 0),
            data.get("fees_exit_target", 0),
            data.get("fees_exit_sl", 0),
            data.get("entry_date", now),
            data.get("notes", ""),
            now,
            now,
        ),
    )
    conn.commit()
    trade_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_trade(trade_id: int) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def list_trades(status: Optional[str] = None, symbol: Optional[str] = None) -> List[dict]:
    conn = _get_conn()
    query = "SELECT * FROM trades WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if symbol:
        query += " AND symbol LIKE ?"
        params.append(f"%{symbol}%")
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_trade(trade_id: int, data: dict) -> Optional[dict]:
    conn = _get_conn()
    existing = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if not existing:
        conn.close()
        return None

    now = datetime.now(timezone.utc).isoformat()
    allowed = {
        "exit_price", "actual_pnl", "actual_fees", "status",
        "exit_date", "notes", "stop_loss", "target",
    }
    sets = ["updated_at = ?"]
    params: list = [now]
    for key, val in data.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            params.append(val)

    params.append(trade_id)
    conn.execute(f"UPDATE trades SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def delete_trade(trade_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_summary() -> dict:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    open_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'").fetchone()[0]
    won = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'WON'").fetchone()[0]
    lost = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'LOST'").fetchone()[0]
    closed = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'").fetchone()[0]

    pnl_row = conn.execute(
        "SELECT COALESCE(SUM(actual_pnl), 0) FROM trades WHERE status IN ('WON', 'LOST', 'CLOSED')"
    ).fetchone()
    net_pnl = pnl_row[0]

    fees_row = conn.execute(
        "SELECT COALESCE(SUM(actual_fees), 0) FROM trades WHERE status IN ('WON', 'LOST', 'CLOSED')"
    ).fetchone()
    total_fees = fees_row[0]

    closed_total = won + lost + closed
    win_rate = (won / closed_total * 100) if closed_total > 0 else 0

    conn.close()
    return {
        "total_trades": total,
        "open_trades": open_count,
        "won": won,
        "lost": lost,
        "closed": closed,
        "win_rate": round(win_rate, 1),
        "net_pnl": round(net_pnl, 2),
        "total_fees": round(total_fees, 2),
    }
