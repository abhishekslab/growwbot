"""
Base algorithm class and AlgoSignal dataclass.

All algo strategies inherit from BaseAlgorithm and implement evaluate().

This module is deprecated. Import from strategies.base instead.
"""

from strategies.base import AlgoSignal, BaseAlgorithm
from strategies.base import calculate_fees

__all__ = ["AlgoSignal", "BaseAlgorithm", "calculate_fees"]
