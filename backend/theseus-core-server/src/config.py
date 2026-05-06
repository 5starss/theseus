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
    SPRING_BOOT_AUTH_VERIFY_URL: str = "http://localhost:8080/api/internal/auth/verify"
    SPRING_BOOT_PROJECT_PERMISSIONS_URL: str = "http://localhost:8080/api/internal/project/permissions"
    SPRING_BOOT_BILLING_USAGE_URL: str = "http://localhost:8080/api/internal/billing/usage"
    SPRING_BOOT_TOOL_PLAN_URL: str = "http://localhost:8080/api/internal/tool-plan/save"
    SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL: str = "http://localhost:8080/api/internal/history/messages"
    SPRING_BOOT_INTERNAL_TOOL_DRAFT_URL: str = "http://localhost:8080/api/internal/tools/{tool_id}/draft"
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

    # Kafka Settings
    CORE_KAFKA_CONSUMER_ENABLED: bool = False
    CORE_KAFKA_BOOTSTRAP_SERVERS: str = "localhost:19092"
    CORE_KAFKA_CONSUMER_GROUP_ID: str = "theseus-core-tool-generation"
    KAFKA_TOPIC_TOOL_GENERATION_REQUEST: str = "theseus.tool-generation.request"
    KAFKA_TOPIC_TOOL_REGENERATION_REQUEST: str = "theseus.tool-regeneration.request"
    KAFKA_TOPIC_TOOL_GENERATION_EVENT: str = "theseus.tool-generation.event"
    
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
