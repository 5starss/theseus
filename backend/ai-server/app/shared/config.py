from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App Settings
    APP_TITLE: str = "AI Server - Trade Edition"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Kafka Settings (if needed in AI server)
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    
    # S3 Settings
    S3_BUCKET: str = "s14-p21a503-bucket"
    S3_REGION: str = "ap-northeast-2"
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_PATH_PREFIX: str = "ai-server/"

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0

    # Core API Settings
    CORE_API_BASE_URL: str = "http://localhost:8080"

    # Strategy Settings
    DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD: int = 30


settings = Settings()
