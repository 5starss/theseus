from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
from typing import Literal

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "TheseusCoreServer"
    ENV: str = "dev"
    
    # Auth Settings
    AUTH_MODE: Literal["mock", "spring"] = "mock"
    SPRING_BOOT_INTERNAL_URL: str = "http://localhost:8080"
    SPRING_BOOT_AUTH_VERIFY_URL: str = "http://localhost:8080/api/auth/verify"
    SPRING_BOOT_BILLING_USAGE_URL: str = "http://localhost:8080/api/internal/billing/usage"
    SPRING_BOOT_TOOL_PLAN_URL: str = "http://localhost:8080/api/internal/tool-plan/save"
    AUTH_TIMEOUT_SECONDS: int = 5
    INTERNAL_API_TIMEOUT_SECONDS: int = 10
    BILLING_OUTBOX_BATCH_SIZE: int = 10
    BILLING_OUTBOX_FLUSH_INTERVAL_SECONDS: int = 30
    
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

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
