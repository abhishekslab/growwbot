"""
Core configuration management using Pydantic Settings.

Loads configuration from environment variables and .env files.
Provides type-safe access to all application settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Groww API credentials
    api_key: str = Field(..., env="API_KEY")
    api_secret: str = Field(..., env="API_SECRET")

    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # Frontend URL for CORS
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")

    # Database settings
    database_path: str = Field(default="trades.db", env="DATABASE_PATH")

    # Token persistence
    token_file: str = Field(default=".auth_token", env="TOKEN_FILE")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Trading settings
    default_capital: float = Field(default=100000.0, env="DEFAULT_CAPITAL")
    default_risk_percent: float = Field(default=1.0, env="DEFAULT_RISK_PERCENT")

    # Paper trading default
    paper_mode_default: bool = Field(default=True, env="PAPER_MODE_DEFAULT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings():
    # type: () -> Settings
    """
    Get cached settings instance.

    Returns:
        Settings instance loaded from environment
    """
    return Settings()


# Convenience exports for backward compatibility
def get_api_credentials():
    # type: () -> tuple[str, str]
    """Get API key and secret as tuple."""
    settings = get_settings()
    return settings.api_key, settings.api_secret


def get_database_path():
    # type: () -> str
    """Get database file path."""
    return get_settings().database_path


def get_token_file():
    # type: () -> str
    """Get token persistence file path."""
    return get_settings().token_file
