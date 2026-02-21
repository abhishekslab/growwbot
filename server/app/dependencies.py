"""
Dependency injection container and providers.

Provides dependency injection for FastAPI using the Depends pattern.
"""

from functools import lru_cache
from typing import Generator

from repositories.trade_repository import TradeRepository
from repositories.algo_repository import AlgoRepository
from services.trade_service import TradeService
from services.algo_service import AlgoService
from services.holdings_service import HoldingsService
from infrastructure.groww_client import get_groww_client, GrowwClientBase


@lru_cache()
def get_trade_repository() -> TradeRepository:
    """Get singleton TradeRepository instance."""
    return TradeRepository()


@lru_cache()
def get_algo_repository() -> AlgoRepository:
    """Get singleton AlgoRepository instance."""
    return AlgoRepository()


def get_trade_service() -> Generator[TradeService, None, None]:
    """
    Get TradeService with injected repository.

    Yields:
        TradeService instance
    """
    repository = get_trade_repository()
    service = TradeService(repository)
    try:
        yield service
    finally:
        pass  # Cleanup if needed


def get_algo_service() -> Generator[AlgoService, None, None]:
    """
    Get AlgoService with injected repository.

    Yields:
        AlgoService instance
    """
    repository = get_algo_repository()
    service = AlgoService(repository)
    try:
        yield service
    finally:
        pass  # Cleanup if needed


# FastAPI dependency providers
def trade_service_dependency():
    """FastAPI dependency for TradeService."""
    repository = get_trade_repository()
    return TradeService(repository)


def algo_service_dependency():
    """FastAPI dependency for AlgoService."""
    repository = get_algo_repository()
    return AlgoService(repository)


def get_groww_client_dep() -> GrowwClientBase:
    """FastAPI dependency for GrowwClient."""
    return get_groww_client()


def get_holdings_service() -> Generator[HoldingsService, None, None]:
    """FastAPI dependency for HoldingsService."""
    client = get_groww_client()
    service = HoldingsService(client)
    try:
        yield service
    finally:
        pass
