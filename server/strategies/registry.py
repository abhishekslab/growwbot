"""
Strategy Registry - Auto-discovery and registration of trading strategies.
"""

import logging
from typing import Dict, List, Optional, Type

from strategies.base import BaseAlgorithm
from strategies.momentum import MomentumScalping
from strategies.mean_reversion import MeanReversion

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Registry for trading strategies with auto-discovery."""

    _strategies: Dict[str, Type[BaseAlgorithm]] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, algo_id: str, strategy_class: Type[BaseAlgorithm]) -> None:
        """Register a strategy class with its algo_id."""
        cls._strategies[algo_id] = strategy_class
        logger.info(f"Registered strategy: {algo_id} -> {strategy_class.__name__}")

    @classmethod
    def get(cls, algo_id: str, config: dict) -> Optional[BaseAlgorithm]:
        """Get a strategy instance by algo_id with config."""
        strategy_class = cls._strategies.get(algo_id)
        if strategy_class is None:
            logger.warning(f"Strategy not found: {algo_id}")
            return None
        return strategy_class(config)

    @classmethod
    def list_strategies(cls) -> List[Dict[str, str]]:
        """List all registered strategies."""
        return [
            {
                "algo_id": algo_id,
                "name": cls.ALGO_NAME,
                "description": cls.DESCRIPTION,
                "version": cls.ALGO_VERSION,
            }
            for algo_id, cls in cls._strategies.items()
        ]

    @classmethod
    def initialize(cls) -> None:
        """Initialize and register all built-in strategies."""
        if cls._initialized:
            return

        cls.register("momentum_scalp", MomentumScalping)
        cls.register("mean_reversion", MeanReversion)

        cls._initialized = True
        logger.info(f"Initialized StrategyRegistry with {len(cls._strategies)} strategies")


def get_strategy(algo_id: str, config: dict) -> Optional[BaseAlgorithm]:
    """Convenience function to get a strategy instance."""
    StrategyRegistry.initialize()
    return StrategyRegistry.get(algo_id, config)


def list_strategies() -> List[Dict[str, str]]:
    """Convenience function to list all available strategies."""
    StrategyRegistry.initialize()
    return StrategyRegistry.list_strategies()
