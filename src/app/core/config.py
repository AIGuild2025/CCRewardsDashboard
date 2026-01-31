"""Application configuration using Pydantic settings."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cc_user:cc_password@localhost:5432/cc_rewards"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://cc_user:cc_password@localhost:5433/cc_rewards_test"

    # Security / JWT
    SECRET_KEY: str = "your-secret-key-here-change-in-production"  # Can use JWT_SECRET from .env
    JWT_SECRET: str | None = None  # Alternative name for SECRET_KEY
    
    def __init__(self, **kwargs):
        """Initialize settings and handle JWT_SECRET fallback."""
        super().__init__(**kwargs)
        # Use JWT_SECRET if provided, otherwise fall back to SECRET_KEY
        if self.JWT_SECRET:
            self.SECRET_KEY = self.JWT_SECRET
    
    # Application
    PROJECT_NAME: str = "CC Rewards Dashboard"
    VERSION: str = "0.1.0"
    DEBUG: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
