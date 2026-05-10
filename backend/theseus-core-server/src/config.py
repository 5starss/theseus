from functools import lru_cache
import os
from typing import Optional
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_INTERNAL_API_KEY = "theseus-local-internal-api-key"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "TheseusCoreServer"
    ENV: Literal["dev", "test", "prod"] = "dev"
    ALLOWED_ORIGINS: list[str] = []

    # Auth Settings
    AUTH_MODE: Literal["mock", "spring"] = "spring"
    SPRING_BOOT_INTERNAL_URL: str = "http://localhost:8080"
    SPRING_BOOT_AUTH_VERIFY_URL: str = "http://localhost:8080/api/internal/auth/verify"
    SPRING_BOOT_PROJECT_PERMISSIONS_URL: str = "http://localhost:8080/api/internal/project/permissions"
    SPRING_BOOT_BILLING_USAGE_URL: str = "http://localhost:8080/api/internal/billing/usage"
    SPRING_BOOT_TOOL_PLAN_URL: str = "http://localhost:8080/api/internal/tool-plan/save"
    SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL: str = "http://localhost:8080/api/internal/history/messages"
    SPRING_BOOT_INTERNAL_API_KEY: str = "theseus-local-internal-api-key"
    AUTH_TIMEOUT_SECONDS: int = 5
    INTERNAL_API_TIMEOUT_SECONDS: int = 10
    BILLING_OUTBOX_BATCH_SIZE: int = 10
    BILLING_OUTBOX_FLUSH_INTERVAL_SECONDS: int = 30
    SANDBOX_IMAGE: str = "python:3.11-slim"
    SANDBOX_MEMORY_LIMIT: str = "128m"
    SANDBOX_CPU_QUOTA: int = 50000
    SANDBOX_CPU_PERIOD: int = 100000
    SANDBOX_KEEP_FAILED_CONTAINERS: bool = False
    DOCKER_HOST: Optional[str] = None
    SANDBOX_STARTUP_CHECK: bool = True
    SANDBOX_STARTUP_STRICT: bool = False
    SANDBOX_PULL_ON_STARTUP: bool = False

    # Kafka Settings
    CORE_KAFKA_CONSUMER_ENABLED: bool = False
    CORE_KAFKA_BOOTSTRAP_SERVERS: str = "localhost:19092"
    CORE_KAFKA_CONSUMER_GROUP_ID: str = "theseus-core-tool-generation"
    CORE_KAFKA_TOOL_BUILD_CONSUMER_GROUP_ID: str = "theseus-core-tool-build"
    KAFKA_TOPIC_TOOL_GENERATION_REQUEST: str = "theseus.tool-generation.request"
    KAFKA_TOPIC_TOOL_REGENERATION_REQUEST: str = "theseus.tool-regeneration.request"
    KAFKA_TOPIC_TOOL_GENERATION_EVENT: str = "theseus.tool-generation.event"
    KAFKA_TOPIC_TOOL_BUILD_REQUEST: str = "theseus.tool-build.request"
    KAFKA_TOPIC_TOOL_BUILD_EVENT: str = "theseus.tool-build.event"
    
    # Database Settings (PostgreSQL + pgvector)
    CORE_POSTGRES_HOST: str = "localhost"
    CORE_POSTGRES_PORT: int = 15432
    CORE_POSTGRES_DB: str = "theseus_core"
    CORE_POSTGRES_USER: str = "root"
    CORE_POSTGRES_PASSWORD: str = "root"
    CORE_POSTGRES_SCHEMA: str = "public"

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.CORE_POSTGRES_USER}:{self.CORE_POSTGRES_PASSWORD}@{self.CORE_POSTGRES_HOST}:{self.CORE_POSTGRES_PORT}/{self.CORE_POSTGRES_DB}"
    
    # RAG Settings
    EMBEDDING_PROVIDER: str = "local" # local | remote
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    VECTOR_DIMENSION: int = 384
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float = 0.3
    
    # AI / Tools Settings (Optional for now)
    OPENAI_API_KEY: Optional[str] = None
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_TRACING: bool = False
    LANGSMITH_PROJECT: str = "theseus-core"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("ALLOWED_ORIGINS must be a comma-separated string or list")

    @property
    def is_production(self) -> bool:
        return self.ENV == "prod"

    @property
    def mock_auth_enabled(self) -> bool:
        return self.AUTH_MODE == "mock"

    @property
    def cors_allowed_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS:
            return self.ALLOWED_ORIGINS
        if not self.is_production:
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        return []

    @property
    def docker_host(self) -> Optional[str]:
        return self.DOCKER_HOST or os.getenv("DOCKER_HOST")

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> "Settings":
        if self.mock_auth_enabled and self.ENV not in {"dev", "test"}:
            raise ValueError("AUTH_MODE=mock is only allowed in dev/test environments")

        if not self.is_production:
            return self

        if self.mock_auth_enabled:
            raise ValueError("AUTH_MODE=mock is not allowed in production")

        required_urls = {
            "SPRING_BOOT_INTERNAL_URL": self.SPRING_BOOT_INTERNAL_URL,
            "SPRING_BOOT_AUTH_VERIFY_URL": self.SPRING_BOOT_AUTH_VERIFY_URL,
            "SPRING_BOOT_PROJECT_PERMISSIONS_URL": self.SPRING_BOOT_PROJECT_PERMISSIONS_URL,
            "SPRING_BOOT_BILLING_USAGE_URL": self.SPRING_BOOT_BILLING_USAGE_URL,
            "SPRING_BOOT_TOOL_PLAN_URL": self.SPRING_BOOT_TOOL_PLAN_URL,
            "SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL": self.SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL,
        }
        for name, value in required_urls.items():
            if not value.strip():
                raise ValueError(f"{name} must be set in production")
            if _is_local_url(value):
                raise ValueError(f"{name} must not point to localhost in production")

        if not self.SPRING_BOOT_INTERNAL_API_KEY.strip():
            raise ValueError("SPRING_BOOT_INTERNAL_API_KEY must be set in production")
        if self.SPRING_BOOT_INTERNAL_API_KEY == DEFAULT_INTERNAL_API_KEY:
            raise ValueError("SPRING_BOOT_INTERNAL_API_KEY must not use the development default in production")

        if not self.ALLOWED_ORIGINS:
            raise ValueError("ALLOWED_ORIGINS must be set in production")
        if any(origin == "*" for origin in self.ALLOWED_ORIGINS):
            raise ValueError("ALLOWED_ORIGINS must not contain '*' in production")

        return self


def _is_local_url(value: str) -> bool:
    hostname = urlparse(value).hostname
    return hostname in LOCAL_HOSTS

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
