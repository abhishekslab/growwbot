"""
Repository base class defining the interface for data access.

All repositories must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class Repository(ABC, Generic[T, ID]):
    """Abstract base class for all repositories."""

    @abstractmethod
    def get_by_id(self, id: ID) -> Optional[T]:
        """Get entity by ID."""
        pass

    @abstractmethod
    def list(self, **filters) -> List[T]:
        """List entities with optional filters."""
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """Create new entity."""
        pass

    @abstractmethod
    def update(self, id: ID, entity: T) -> Optional[T]:
        """Update existing entity."""
        pass

    @abstractmethod
    def delete(self, id: ID) -> bool:
        """Delete entity by ID."""
        pass

    @abstractmethod
    def exists(self, id: ID) -> bool:
        """Check if entity exists."""
        pass


class UnitOfWork(ABC):
    """Abstract base for unit of work pattern."""

    @abstractmethod
    def commit(self) -> None:
        """Commit current transaction."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback current transaction."""
        pass

    @abstractmethod
    def __enter__(self):
        """Enter context manager."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        pass
