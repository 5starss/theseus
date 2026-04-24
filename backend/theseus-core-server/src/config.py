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
    AUTH_TIMEOUT_SECONDS: int = 5
    
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
