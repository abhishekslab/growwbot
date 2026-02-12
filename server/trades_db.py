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

    # Migration: add order_status column (idempotent)
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN order_status TEXT DEFAULT 'PLACED'")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migration: add groww_order_id column (idempotent)
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN groww_order_id TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migration: add is_paper column (idempotent)
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN is_paper INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_is_paper ON trades(is_paper)")

    # Migration: add entry_snapshot column (JSON blob of analysis context at trade entry)
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN entry_snapshot TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migration: add exit_trigger column (SL, TARGET, MANUAL)
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN exit_trigger TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists

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
            status, order_status, groww_order_id, is_paper, entry_date, notes,
            entry_snapshot, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get("status", "OPEN"),
            data.get("order_status", "PLACED"),
            data.get("groww_order_id"),
            data.get("is_paper", 0),
            data.get("entry_date", now),
            data.get("notes", ""),
            data.get("entry_snapshot"),
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


def list_trades(status: Optional[str] = None, symbol: Optional[str] = None, is_paper: Optional[bool] = None) -> List[dict]:
    conn = _get_conn()
    query = "SELECT * FROM trades WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if symbol:
        query += " AND symbol LIKE ?"
        params.append(f"%{symbol}%")
    if is_paper is not None:
        query += " AND is_paper = ?"
        params.append(1 if is_paper else 0)
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
        "exit_date", "notes", "stop_loss", "target", "order_status",
        "groww_order_id", "exit_trigger",
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


def get_realized_pnl(is_paper: Optional[bool] = None) -> dict:
    conn = _get_conn()
    query = "SELECT COALESCE(SUM(actual_pnl), 0), COALESCE(SUM(actual_fees), 0), COUNT(*) FROM trades WHERE status IN ('WON', 'LOST', 'CLOSED')"
    params: list = []
    if is_paper is not None:
        query += " AND is_paper = ?"
        params.append(1 if is_paper else 0)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return {
        "realized_pnl": round(row[0], 2),
        "total_fees": round(row[1], 2),
        "trade_count": row[2],
    }


def get_learning_analytics(is_paper: Optional[bool] = None) -> dict:
    conn = _get_conn()
    paper_clause = ""
    params = []  # type: list
    if is_paper is not None:
        paper_clause = " AND is_paper = ?"
        params = [1 if is_paper else 0]

    closed_clause = "status IN ('WON', 'LOST', 'CLOSED')"

    # Win rate by confidence
    by_confidence = []
    try:
        rows = conn.execute(
            "SELECT json_extract(entry_snapshot, '$.confidence') as conf, "
            "COUNT(*) as total, "
            "SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as won, "
            "ROUND(AVG(actual_pnl), 2) as avg_pnl "
            "FROM trades WHERE " + closed_clause + " AND entry_snapshot IS NOT NULL" + paper_clause +
            " GROUP BY conf ORDER BY total DESC",
            params,
        ).fetchall()
        for r in rows:
            if r[0]:
                by_confidence.append({
                    "confidence": r[0], "total": r[1], "won": r[2],
                    "win_pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0,
                    "avg_pnl": r[3] or 0,
                })
    except Exception:
        pass

    # Win rate by verdict
    by_verdict = []
    try:
        rows = conn.execute(
            "SELECT json_extract(entry_snapshot, '$.verdict') as verd, "
            "COUNT(*) as total, "
            "SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as won, "
            "ROUND(AVG(actual_pnl), 2) as avg_pnl "
            "FROM trades WHERE " + closed_clause + " AND entry_snapshot IS NOT NULL" + paper_clause +
            " GROUP BY verd ORDER BY total DESC",
            params,
        ).fetchall()
        for r in rows:
            if r[0]:
                by_verdict.append({
                    "verdict": r[0], "total": r[1], "won": r[2],
                    "win_pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0,
                    "avg_pnl": r[3] or 0,
                })
    except Exception:
        pass

    # Win rate by trend
    by_trend = []
    try:
        rows = conn.execute(
            "SELECT json_extract(entry_snapshot, '$.trend') as tr, "
            "COUNT(*) as total, "
            "SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as won, "
            "ROUND(AVG(actual_pnl), 2) as avg_pnl "
            "FROM trades WHERE " + closed_clause + " AND entry_snapshot IS NOT NULL" + paper_clause +
            " GROUP BY tr ORDER BY total DESC",
            params,
        ).fetchall()
        for r in rows:
            if r[0]:
                by_trend.append({
                    "trend": r[0], "total": r[1], "won": r[2],
                    "win_pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0,
                    "avg_pnl": r[3] or 0,
                })
    except Exception:
        pass

    # Exit trigger distribution
    by_exit_trigger = []
    try:
        rows = conn.execute(
            "SELECT exit_trigger, COUNT(*) as total "
            "FROM trades WHERE " + closed_clause + paper_clause +
            " GROUP BY exit_trigger ORDER BY total DESC",
            params,
        ).fetchall()
        for r in rows:
            by_exit_trigger.append({
                "trigger": r[0] or "UNKNOWN", "total": r[1],
            })
    except Exception:
        pass

    # Overreach stats (trades with target warnings)
    overreach_stats = {"total": 0, "won": 0, "win_pct": 0}
    try:
        row = conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) as won "
            "FROM trades WHERE " + closed_clause + " AND entry_snapshot IS NOT NULL"
            " AND (entry_snapshot LIKE '%TARGET_ABOVE%' OR entry_snapshot LIKE '%EXCEEDS_TYPICAL%')" + paper_clause,
            params,
        ).fetchone()
        if row and row[0] > 0:
            overreach_stats = {
                "total": row[0], "won": row[1],
                "win_pct": round(row[1] / row[0] * 100, 1),
            }
    except Exception:
        pass

    conn.close()
    return {
        "by_confidence": by_confidence,
        "by_verdict": by_verdict,
        "by_trend": by_trend,
        "by_exit_trigger": by_exit_trigger,
        "overreach_stats": overreach_stats,
    }


def get_summary(is_paper: Optional[bool] = None) -> dict:
    conn = _get_conn()
    paper_clause = ""
    params: list = []
    if is_paper is not None:
        paper_clause = " AND is_paper = ?"
        params = [1 if is_paper else 0]

    total = conn.execute("SELECT COUNT(*) FROM trades WHERE 1=1" + paper_clause, params).fetchone()[0]
    open_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'" + paper_clause, params).fetchone()[0]
    won = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'WON'" + paper_clause, params).fetchone()[0]
    lost = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'LOST'" + paper_clause, params).fetchone()[0]
    closed = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'" + paper_clause, params).fetchone()[0]

    pnl_row = conn.execute(
        "SELECT COALESCE(SUM(actual_pnl), 0) FROM trades WHERE status IN ('WON', 'LOST', 'CLOSED')" + paper_clause, params
    ).fetchone()
    net_pnl = pnl_row[0]

    fees_row = conn.execute(
        "SELECT COALESCE(SUM(actual_fees), 0) FROM trades WHERE status IN ('WON', 'LOST', 'CLOSED')" + paper_clause, params
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
