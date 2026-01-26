from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        case_sensitive=False,
    )
    
    # Application
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str
    db_echo: bool = False
    
    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    
    # Parsing
    pdf_max_size_mb: int = 25
    parse_timeout_seconds: int = 60
    
    # PII Masking
    presidio_confidence: float = 0.7

    # Money / amounts
    currency: str = "INR"
    currency_minor_unit: int = 2


settings = Settings()
