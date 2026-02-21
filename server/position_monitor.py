"""
Background position monitor.

This module is deprecated. Import from services.position_monitor instead.
"""

from services.position_monitor import PositionMonitor, get_position_monitor
from utils.fees import calculate_fees, compute_exit_pnl

__all__ = ["PositionMonitor", "get_position_monitor", "calculate_fees", "compute_exit_pnl"]
