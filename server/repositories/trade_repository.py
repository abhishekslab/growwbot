"""
Trade repository implementation using SQLite.

Wraps trades_db functions with repository pattern.
Works with or without pydantic domain models installed.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from repositories.base import Repository
import trades_db

# Try to import domain models, fall back to dict if not available
try:
    from domain.models import Trade, TradeCreate, TradeUpdate, TradeFilter, TradeSummary

    USE_PYDANTIC = True
except ImportError:
    Trade = dict
    TradeCreate = dict
    TradeUpdate = dict
    TradeFilter = dict
    TradeSummary = dict
    USE_PYDANTIC = False


class TradeRepository(Repository[Trade, int]):
    """Repository for trade operations."""

    def get_by_id(self, id: int) -> Optional[Trade]:
        """Get trade by ID."""
        row = trades_db.get_trade(id)
        if row:
            if USE_PYDANTIC:
                return Trade(**row)
            return row
        return None

    def list(self, filter: Optional[TradeFilter] = None, **kwargs) -> List[Trade]:
        """List trades with optional filters."""
        if USE_PYDANTIC and filter is not None:
            rows = trades_db.list_trades(status=filter.status, symbol=filter.symbol, is_paper=filter.is_paper, algo_id=filter.algo_id)
        else:
            rows = trades_db.list_trades(**kwargs)

        if USE_PYDANTIC:
            return [Trade(**row) for row in rows]
        return rows

    def create(self, trade: TradeCreate) -> Trade:
        """Create new trade."""
        if USE_PYDANTIC:
            data = trade.dict()
        else:
            data = trade

        # Set default entry_date if not provided
        if not data.get("entry_date"):
            data["entry_date"] = datetime.now(timezone.utc).isoformat()

        row = trades_db.create_trade(data)
        if USE_PYDANTIC:
            return Trade(**row)
        return row

    def update(self, id: int, trade_update: TradeUpdate) -> Optional[Trade]:
        """Update existing trade."""
        if USE_PYDANTIC:
            # Only include non-None fields
            data = {k: v for k, v in trade_update.dict().items() if v is not None}
        else:
            data = trade_update

        if not data:
            return self.get_by_id(id)

        row = trades_db.update_trade(id, data)
        if row:
            if USE_PYDANTIC:
                return Trade(**row)
            return row
        return None

    def delete(self, id: int) -> bool:
        """Delete trade by ID."""
        return trades_db.delete_trade(id)

    def exists(self, id: int) -> bool:
        """Check if trade exists."""
        return trades_db.get_trade(id) is not None

    def get_open_trades(self, is_paper: Optional[bool] = None) -> List[Trade]:
        """Get all open trades."""
        return self.list(status="OPEN", is_paper=is_paper)

    def get_trades_by_symbol(self, symbol: str, status: Optional[str] = None) -> List[Trade]:
        """Get trades for a specific symbol."""
        return self.list(symbol=symbol, status=status)

    def close_trade(
        self, id: int, exit_price: float, exit_trigger: str, actual_pnl: Optional[float] = None, actual_fees: Optional[float] = None
    ) -> Optional[Trade]:
        """Close a trade with exit details."""
        if USE_PYDANTIC:
            from domain.models import TradeUpdate

            update_data = TradeUpdate(
                status="CLOSED",
                exit_price=exit_price,
                exit_trigger=exit_trigger,
                actual_pnl=actual_pnl,
                actual_fees=actual_fees,
                exit_date=datetime.now(timezone.utc).isoformat(),
            )
        else:
            update_data = {
                "status": "CLOSED",
                "exit_price": exit_price,
                "exit_trigger": exit_trigger,
                "actual_pnl": actual_pnl,
                "actual_fees": actual_fees,
                "exit_date": datetime.now(timezone.utc).isoformat(),
            }

        return self.update(id, update_data)

    def get_summary(self, is_paper: Optional[bool] = None) -> TradeSummary:
        """Get trade summary statistics."""
        data = trades_db.get_summary(is_paper=is_paper)
        mapped = {
            "total_trades": data.get("total_trades", 0),
            "open_trades": data.get("open_trades", 0),
            "won_trades": data.get("won", 0),
            "lost_trades": data.get("lost", 0),
            "win_rate": data.get("win_rate", 0.0),
            "total_pnl": data.get("net_pnl", 0),
            "avg_pnl": data.get("net_pnl", 0) / max(data.get("won", 0) + data.get("lost", 0), 1),
            "max_profit": 0.0,
            "max_loss": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
        }
        if USE_PYDANTIC:
            return TradeSummary(**mapped)
        return mapped

    def get_realized_pnl(self, is_paper: Optional[bool] = None) -> Dict[str, Any]:
        """Get realized PnL statistics."""
        return trades_db.get_realized_pnl(is_paper=is_paper)

    def update_order_status(self, id: int, order_status: str, groww_order_id: Optional[str] = None) -> Optional[Trade]:
        """Update order status for a trade."""
        data = {"order_status": order_status}
        if groww_order_id:
            data["groww_order_id"] = groww_order_id

        row = trades_db.update_trade(id, data)
        if row:
            if USE_PYDANTIC:
                return Trade(**row)
            return row
        return None

    def get_learning_analytics(self, is_paper: Optional[bool] = None) -> Dict[str, Any]:
        """Get learning analytics."""
        return trades_db.get_learning_analytics(is_paper=is_paper)
