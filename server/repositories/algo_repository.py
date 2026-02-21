"""
Algorithm repository implementation using SQLite.

Wraps algo-related database operations from trades_db.
Works with or without pydantic domain models installed.
"""

from typing import List, Optional, Dict, Any

import trades_db

# Try to import domain models, fall back to dict if not available
try:
    from domain.models import AlgoSignal, AlgoSettings, AlgoConfig

    USE_PYDANTIC = True
except ImportError:
    AlgoSignal = dict
    AlgoSettings = dict
    AlgoConfig = dict
    USE_PYDANTIC = False


def _map_db_to_algo_settings(row: dict) -> AlgoSettings:
    """Map flat DB row to nested AlgoSettings model."""
    if not USE_PYDANTIC:
        return row

    return AlgoSettings(
        algo_id=row.get("algo_id", ""),
        enabled=bool(row.get("enabled", 1)),
        config=AlgoConfig(
            capital=row.get("capital", 100000),
            risk_percent=row.get("risk_percent", 1),
            max_positions_per_algo=row.get("max_positions_per_algo", 3),
            max_total_positions=row.get("max_total_positions", 6),
            trading_start_ist=row.get("trading_start_ist", "09:30"),
            trading_end_ist=row.get("trading_end_ist", "15:00"),
            force_close_ist=row.get("force_close_ist", "15:15"),
            max_trade_duration_minutes=row.get("max_trade_duration_minutes", 15),
        ),
    )


class AlgoRepository:
    """Repository for algorithm-related operations."""

    def save_signal(self, signal: AlgoSignal) -> AlgoSignal:
        """Save an algorithm signal/decision."""
        if USE_PYDANTIC:
            data = {
                "timestamp": signal.timestamp,
                "algo_id": signal.algo_id,
                "symbol": signal.symbol,
                "decision": signal.decision,
                "reason": signal.reason,
                "confidence": signal.confidence,
                "metadata": signal.metadata,
            }
        else:
            data = signal

        trades_db.save_algo_signal(data)
        return signal

    def list_signals(self, algo_id: Optional[str] = None, limit: int = 50, exclude_skips: bool = True) -> List[AlgoSignal]:
        """List algorithm signals."""
        rows = trades_db.list_algo_signals(algo_id=algo_id, limit=limit, exclude_skips=exclude_skips)
        if USE_PYDANTIC:
            return [AlgoSignal(**row) for row in rows]
        return rows

    def get_settings(self, algo_id: str) -> Optional[AlgoSettings]:
        """Get algorithm settings."""
        row = trades_db.get_algo_settings(algo_id)
        if row:
            if USE_PYDANTIC:
                return _map_db_to_algo_settings(row)
            return row
        return None

    def get_all_settings(self) -> Dict[str, AlgoSettings]:
        """Get settings for all algorithms."""
        rows = trades_db.get_all_algo_settings()
        if USE_PYDANTIC:
            result = {}
            for row in rows:
                algo_id = row.get("algo_id")
                if algo_id:
                    result[algo_id] = _map_db_to_algo_settings(row)
            return result
        return {row.get("algo_id", ""): row for row in rows if row.get("algo_id")}

    def upsert_settings(self, algo_id: str, settings: AlgoSettings) -> AlgoSettings:
        """Create or update algorithm settings."""
        if USE_PYDANTIC:
            data = settings.dict()
        else:
            data = settings

        trades_db.upsert_algo_settings(algo_id, data)
        return settings

    def get_performance(self, is_paper: Optional[bool] = None, group_by_version: bool = False) -> Dict[str, Any]:
        """Get algorithm performance metrics."""
        return trades_db.get_algo_performance(is_paper=is_paper, group_by_version=group_by_version)

    def get_deployed_capital(self, algo_id: str, is_paper: bool = True) -> float:
        """Get deployed capital for an algorithm."""
        return trades_db.get_algo_deployed_capital(algo_id, is_paper)

    def get_net_pnl(self, algo_id: str, is_paper: bool = True) -> float:
        """Get net PnL for an algorithm."""
        return trades_db.get_algo_net_pnl(algo_id, is_paper)
