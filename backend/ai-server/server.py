import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI
from app.api.v1.api import api_router
from app.shared.config import settings
from app.shared.infra.logging import setup_logging
from app.trading.scheduler_instance import scheduler

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("서버 시작: 정기 배치 스케줄러 가동")
    scheduler.start()
    yield
    # Shutdown
    logger.info("서버 종료: 배치 스케줄러 중지")
    scheduler.shutdown()


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Health Check
@app.get("/health", tags=["common"])
async def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "message": f"{settings.APP_TITLE} is running",
        "version": settings.APP_VERSION,
    }

# API Routers
app.include_router(api_router, prefix="/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
