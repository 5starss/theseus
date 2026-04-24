from fastapi import APIRouter
from src.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "env": settings.ENV,
        "version": "0.1.0"
    }
