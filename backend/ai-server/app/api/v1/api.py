from fastapi import APIRouter
from app.api.v1.endpoints import quant, trade

api_router = APIRouter()
api_router.include_router(quant.router, prefix="/quant", tags=["quant"])
api_router.include_router(trade.router, prefix="/trade", tags=["trade"])
