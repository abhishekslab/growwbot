"""
Persistence layer for backtest run history.

Uses the same SQLite DB as backtest_cache (backtest_cache.db).
"""

import json
import sqlite3
from typing import List, Optional

from backtest_cache import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            algo_id TEXT NOT NULL,
            groww_symbol TEXT NOT NULL,
            exchange TEXT NOT NULL,
            segment TEXT NOT NULL,
            interval TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            config_json TEXT,
            metrics_json TEXT,
            trades_json TEXT,
            equity_curve_json TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_backtest_runs_algo_id ON backtest_runs(algo_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at)"
    )
    conn.commit()


def save_backtest_run(
    algo_id: str,
    groww_symbol: str,
    exchange: str,
    segment: str,
    interval: str,
    start_date: str,
    end_date: str,
    config: Optional[dict] = None,
    metrics: Optional[dict] = None,
    trades: Optional[List[dict]] = None,
    equity_curve: Optional[List[dict]] = None,
) -> int:
    """Save a backtest run. Returns the new row id."""
    from datetime import datetime, timezone
    conn = _get_conn()
    _init_schema(conn)
    created_at = datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(config) if config else None
    metrics_json = json.dumps(metrics) if metrics else None
    trades_json = json.dumps(trades) if trades else None
    equity_curve_json = json.dumps(equity_curve) if equity_curve else None
    cursor = conn.execute(
        """INSERT INTO backtest_runs (
            algo_id, groww_symbol, exchange, segment, interval,
            start_date, end_date, config_json, metrics_json, trades_json,
            equity_curve_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            algo_id,
            groww_symbol,
            exchange,
            segment,
            interval,
            start_date,
            end_date,
            config_json,
            metrics_json,
            trades_json,
            equity_curve_json,
            created_at,
        ),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id or 0


def list_backtest_runs(limit: int = 50) -> List[dict]:
    """List past runs (summary: id, algo_id, symbol, dates, key metrics)."""
    conn = _get_conn()
    _init_schema(conn)
    cursor = conn.execute(
        """SELECT id, algo_id, groww_symbol, exchange, segment, interval,
                  start_date, end_date, metrics_json, created_at
           FROM backtest_runs
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    out = []
    for row in rows:
        metrics = {}
        if row["metrics_json"]:
            try:
                metrics = json.loads(row["metrics_json"])
            except Exception:
                pass
        out.append({
            "id": row["id"],
            "algo_id": row["algo_id"],
            "groww_symbol": row["groww_symbol"],
            "exchange": row["exchange"],
            "segment": row["segment"],
            "interval": row["interval"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "metrics": metrics,
            "created_at": row["created_at"],
        })
    return out


def get_backtest_run(run_id: int) -> Optional[dict]:
    """Get full results for a run."""
    conn = _get_conn()
    _init_schema(conn)
    cursor = conn.execute(
        """SELECT id, algo_id, groww_symbol, exchange, segment, interval,
                  start_date, end_date, config_json, metrics_json, trades_json,
                  equity_curve_json, created_at
           FROM backtest_runs WHERE id = ?""",
        (run_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    result = {
        "id": row["id"],
        "algo_id": row["algo_id"],
        "groww_symbol": row["groww_symbol"],
        "exchange": row["exchange"],
        "segment": row["segment"],
        "interval": row["interval"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "created_at": row["created_at"],
    }
    for key, jkey in [
        ("config", "config_json"),
        ("metrics", "metrics_json"),
        ("trades", "trades_json"),
        ("equity_curve", "equity_curve_json"),
    ]:
        val = row[jkey]
        if val:
            try:
                result[key] = json.loads(val)
            except Exception:
                result[key] = None
        else:
            result[key] = None
    return result


def delete_backtest_run(run_id: int) -> bool:
    """Delete a run. Returns True if a row was deleted."""
    conn = _get_conn()
    _init_schema(conn)
    cursor = conn.execute("DELETE FROM backtest_runs WHERE id = ?", (run_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0
