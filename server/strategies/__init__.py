"""
Trading strategies module.

Provides base classes and implementations for algorithmic trading strategies.
"""

from strategies.base import AlgoSignal, BaseAlgorithm
from strategies.momentum import MomentumScalping
from strategies.mean_reversion import MeanReversion
from strategies.registry import StrategyRegistry, get_strategy, list_strategies

__all__ = [
    "AlgoSignal",
    "BaseAlgorithm",
    "MomentumScalping",
    "MeanReversion",
    "StrategyRegistry",
    "get_strategy",
    "list_strategies",
]
