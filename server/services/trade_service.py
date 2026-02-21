"""
Trade service containing business logic for trade operations.

This service abstracts business logic away from API routes and repositories.
Works with or without pydantic domain models installed.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from core.logging_config import get_logger, log_error
from repositories.trade_repository import TradeRepository
from utils.fees import calculate_fees, compute_exit_pnl

logger = get_logger("services.trade")

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


class TradeService:
    """Service for trade business logic."""

    def __init__(self, repository: TradeRepository):
        self.repository = repository

    def create_trade(self, trade_data: TradeCreate) -> Trade:
        """
        Create a new trade with fee calculations.

        Args:
            trade_data: Trade creation data

        Returns:
            Created trade
        """
        if USE_PYDANTIC:
            # Calculate entry fees
            fees_entry = calculate_fees(price=trade_data.entry_price, qty=trade_data.quantity, side="BUY", trade_type=trade_data.trade_type)

            # Calculate exit fee estimates for both target and stop loss
            fees_exit_target = calculate_fees(price=trade_data.target, qty=trade_data.quantity, side="SELL", trade_type=trade_data.trade_type)

            fees_exit_sl = calculate_fees(price=trade_data.stop_loss, qty=trade_data.quantity, side="SELL", trade_type=trade_data.trade_type)

            # Update trade data with calculated fees
            trade_data.fees_entry = fees_entry["total"]
            trade_data.fees_exit_target = fees_exit_target["total"]
            trade_data.fees_exit_sl = fees_exit_sl["total"]
        else:
            # For dict mode, calculate fees and add to dict
            fees_entry = calculate_fees(
                price=trade_data.get("entry_price", 0),
                qty=trade_data.get("quantity", 0),
                side="BUY",
                trade_type=trade_data.get("trade_type", "DELIVERY"),
            )
            trade_data["fees_entry"] = fees_entry["total"]

        trade = self.repository.create(trade_data)
        if USE_PYDANTIC:
            logger.info(
                f"Created trade #{trade.id} for {trade.symbol}", extra={"trade_id": trade.id, "symbol": trade.symbol, "quantity": trade.quantity}
            )
        else:
            trade_id = trade.get("id")
            symbol = trade.get("symbol")
            logger.info(f"Created trade #{trade_id} for {symbol}", extra={"trade_id": trade_id, "symbol": symbol, "quantity": trade.get("quantity")})
        return trade

    def get_trade(self, trade_id: int) -> Optional[Trade]:
        """Get a trade by ID."""
        return self.repository.get_by_id(trade_id)

    def list_trades(self, status: Optional[str] = None, symbol: Optional[str] = None, is_paper: Optional[bool] = None) -> List[Trade]:
        """List trades with filters."""
        if USE_PYDANTIC:
            filter_data = TradeFilter(status=status, symbol=symbol, is_paper=is_paper)
        else:
            filter_data = {"status": status, "symbol": symbol, "is_paper": is_paper}
        return self.repository.list(filter_data)

    def get_open_trades(self, is_paper: Optional[bool] = None) -> List[Trade]:
        """Get all open trades."""
        return self.repository.get_open_trades(is_paper)

    def update_trade(self, trade_id: int, update_data: TradeUpdate) -> Optional[Trade]:
        """Update a trade."""
        trade = self.repository.update(trade_id, update_data)
        if trade:
            logger.info(f"Updated trade #{trade_id}")
        return trade

    def close_trade(self, trade_id: int, exit_price: float, exit_trigger: str) -> Optional[Trade]:
        """
        Close a trade and calculate P&L.

        Args:
            trade_id: Trade ID to close
            exit_price: Exit price
            exit_trigger: Reason for exit (SL, TARGET, MANUAL)

        Returns:
            Updated trade or None if not found
        """
        trade = self.repository.get_by_id(trade_id)
        if not trade:
            logger.warning(f"Attempted to close non-existent trade", extra={"trade_id": trade_id, "action": "close_trade"})
            return None

        if USE_PYDANTIC:
            # Calculate P&L and fees
            net_pnl, total_fees = compute_exit_pnl(
                entry_price=trade.entry_price, exit_price=exit_price, quantity=trade.quantity, trade_type=trade.trade_type
            )

            # Determine status based on P&L
            status = "WON" if net_pnl > 0 else "LOST"

            # Update trade
            update_data = TradeUpdate(
                status=status,
                exit_price=exit_price,
                exit_trigger=exit_trigger,
                actual_pnl=net_pnl,
                actual_fees=total_fees,
                exit_date=datetime.now(timezone.utc).isoformat(),
            )
        else:
            # For dict mode
            net_pnl, total_fees = compute_exit_pnl(
                entry_price=trade.get("entry_price", 0),
                exit_price=exit_price,
                quantity=trade.get("quantity", 0),
                trade_type=trade.get("trade_type", "DELIVERY"),
            )
            status = "WON" if net_pnl > 0 else "LOST"
            update_data = {
                "status": status,
                "exit_price": exit_price,
                "exit_trigger": exit_trigger,
                "actual_pnl": net_pnl,
                "actual_fees": total_fees,
                "exit_date": datetime.now(timezone.utc).isoformat(),
            }

        closed_trade = self.repository.update(trade_id, update_data)
        logger.info(
            f"Closed trade #{trade_id} as {status}",
            extra={
                "trade_id": trade_id,
                "status": status,
                "net_pnl": net_pnl,
                "total_fees": total_fees,
                "exit_price": exit_price,
                "exit_trigger": exit_trigger,
            },
        )
        return closed_trade

    def delete_trade(self, trade_id: int) -> bool:
        """Delete a trade."""
        return self.repository.delete(trade_id)

    def get_summary(self, is_paper: Optional[bool] = None) -> TradeSummary:
        """Get trade summary statistics."""
        return self.repository.get_summary(is_paper)

    def get_realized_pnl(self, is_paper: Optional[bool] = None) -> Dict[str, Any]:
        """Get realized P&L statistics."""
        return self.repository.get_realized_pnl(is_paper)

    def get_learning_analytics(self, is_paper: Optional[bool] = None) -> Dict[str, Any]:
        """Get learning analytics."""
        return self.repository.get_learning_analytics(is_paper)

    def validate_exit_conditions(self, trade: Trade, current_price: float) -> Tuple[bool, Optional[str]]:
        """
        Check if exit conditions are met for a trade.

        Args:
            trade: Trade to check
            current_price: Current market price

        Returns:
            Tuple of (should_exit, trigger_reason)
        """
        if USE_PYDANTIC:
            if trade.status != "OPEN":
                return False, None

            is_long = trade.entry_price > trade.stop_loss

            if is_long:
                if current_price <= trade.stop_loss:
                    return True, "SL"
                elif current_price >= trade.target:
                    return True, "TARGET"
            else:
                if current_price >= trade.stop_loss:
                    return True, "SL"
                elif current_price <= trade.target:
                    return True, "TARGET"
        else:
            if trade.get("status") != "OPEN":
                return False, None

            is_long = trade.get("entry_price", 0) > trade.get("stop_loss", 0)

            if is_long:
                if current_price <= trade.get("stop_loss", 0):
                    return True, "SL"
                elif current_price >= trade.get("target", 0):
                    return True, "TARGET"
            else:
                if current_price >= trade.get("stop_loss", 0):
                    return True, "SL"
                elif current_price <= trade.get("target", 0):
                    return True, "TARGET"

        return False, None

    def get_position_value(self, trade: Trade, current_price: float) -> float:
        """Calculate current position value."""
        if USE_PYDANTIC:
            return current_price * trade.quantity
        else:
            return current_price * trade.get("quantity", 0)

    def get_unrealized_pnl(self, trade: Trade, current_price: float) -> float:
        """Calculate unrealized P&L for an open position."""
        if USE_PYDANTIC:
            return (current_price - trade.entry_price) * trade.quantity
        else:
            return (current_price - trade.get("entry_price", 0)) * trade.get("quantity", 0)
