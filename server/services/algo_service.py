"""
Algorithm service for managing trading algorithms.

Coordinates algorithm lifecycle, signals, and performance tracking.
Works with or without pydantic domain models installed.
"""

from typing import List, Optional, Dict, Any

from core.logging_config import get_logger, log_error
from repositories.algo_repository import AlgoRepository

logger = get_logger("services.algo")

# Try to import domain models, fall back to dict if not available
try:
    from domain.models import AlgoSettings, AlgoSignal, AlgoStatus, AlgoPerformance

    USE_PYDANTIC = True
except ImportError:
    AlgoSettings = dict
    AlgoSignal = dict
    AlgoStatus = dict
    AlgoPerformance = dict
    USE_PYDANTIC = False


class AlgoService:
    """Service for algorithm management."""

    def __init__(self, repository: AlgoRepository):
        self.repository = repository

    def get_settings(self, algo_id: str) -> Optional[AlgoSettings]:
        """Get algorithm settings."""
        return self.repository.get_settings(algo_id)

    def get_all_settings(self) -> Dict[str, AlgoSettings]:
        """Get all algorithm settings."""
        return self.repository.get_all_settings()

    def update_settings(self, algo_id: str, settings: AlgoSettings) -> AlgoSettings:
        """Update algorithm settings."""
        updated = self.repository.upsert_settings(algo_id, settings)
        enabled = updated.enabled if hasattr(updated, "enabled") else updated.get("enabled")
        logger.info(f"Updated settings for algo {algo_id}", extra={"algo_id": algo_id, "enabled": enabled})
        return updated

    def enable_algo(self, algo_id: str) -> AlgoSettings:
        """Enable an algorithm."""
        settings = self.get_settings(algo_id)
        if USE_PYDANTIC:
            if settings is None:
                settings = AlgoSettings(enabled=True)
            settings.enabled = True
        else:
            if settings is None:
                settings = {"enabled": True}
            settings["enabled"] = True
        return self.update_settings(algo_id, settings)

    def disable_algo(self, algo_id: str) -> AlgoSettings:
        """Disable an algorithm."""
        settings = self.get_settings(algo_id)
        if USE_PYDANTIC:
            if settings is None:
                settings = AlgoSettings(enabled=False)
            settings.enabled = False
        else:
            if settings is None:
                settings = {"enabled": False}
            settings["enabled"] = False
        return self.update_settings(algo_id, settings)

    def record_signal(self, signal: AlgoSignal) -> AlgoSignal:
        """Record an algorithm signal/decision."""
        saved = self.repository.save_signal(signal)
        if USE_PYDANTIC:
            logger.info(
                f"Recorded {signal.decision} signal",
                extra={"algo_id": signal.algo_id, "symbol": signal.symbol, "decision": signal.decision, "confidence": signal.confidence},
            )
        else:
            logger.debug(f"Recorded signal: {signal}")
        return saved

    def get_signals(self, algo_id: Optional[str] = None, limit: int = 50, exclude_skips: bool = True) -> List[AlgoSignal]:
        """Get algorithm signals."""
        return self.repository.list_signals(algo_id, limit, exclude_skips)

    def get_performance(self, is_paper: Optional[bool] = None, group_by_version: bool = False) -> Dict[str, Any]:
        """Get algorithm performance metrics."""
        return self.repository.get_performance(is_paper, group_by_version)

    def get_deployed_capital(self, algo_id: str, is_paper: bool = True) -> float:
        """Get deployed capital for an algorithm."""
        return self.repository.get_deployed_capital(algo_id, is_paper)

    def get_net_pnl(self, algo_id: str, is_paper: bool = True) -> float:
        """Get net PnL for an algorithm."""
        return self.repository.get_net_pnl(algo_id, is_paper)

    def is_trading_allowed(self, algo_id: str, current_open_positions: int, total_open_positions: int) -> bool:
        """
        Check if trading is allowed based on algorithm settings.

        Args:
            algo_id: Algorithm ID
            current_open_positions: Current open positions for this algo
            total_open_positions: Total open positions across all algos

        Returns:
            True if trading is allowed
        """
        settings = self.get_settings(algo_id)
        if not settings:
            return False

        if USE_PYDANTIC:
            if not settings.enabled:
                return False

            config = settings.config

            # Check position limits
            if current_open_positions >= config.max_positions_per_algo:
                return False

            if total_open_positions >= config.max_total_positions:
                return False
        else:
            if not settings.get("enabled", False):
                return False

            config = settings.get("config", {})

            # Check position limits
            if current_open_positions >= config.get("max_positions_per_algo", 3):
                return False

            if total_open_positions >= config.get("max_total_positions", 6):
                return False

        return True
