from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.builder.worker import setup_scheduler
from src.config import settings
from src.db.postgres import init_db
from src.routes import health, plan, remote_workspace, sandbox, stream
from src.sandbox.base import SandboxUnavailableError
from src.sandbox.docker_executor import DockerExecutor, SandboxStartupCheckError
from src.tool_build.consumer import start_tool_build_consumer
from src.tool_generation.consumer import start_tool_generation_consumer
from src.tool_plan.consumer import start_tool_plan_consumer
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
_sandbox_executor = DockerExecutor()


def _initial_consumer_status() -> dict[str, dict]:
    return {
        "toolGeneration": {
            "enabled": (
                settings.CORE_KAFKA_CONSUMER_ENABLED
                and settings.CORE_LEGACY_TOOL_GENERATION_CONSUMER_ENABLED
            ),
            "started": False,
            "topics": [
                settings.KAFKA_TOPIC_TOOL_GENERATION_REQUEST,
                settings.KAFKA_TOPIC_TOOL_REGENERATION_REQUEST,
            ],
            "groupId": settings.CORE_KAFKA_CONSUMER_GROUP_ID,
            "error": None,
        },
        "toolPlan": {
            "enabled": (
                settings.CORE_KAFKA_CONSUMER_ENABLED
                and settings.CORE_TOOL_PLAN_CONSUMER_ENABLED
            ),
            "started": False,
            "topic": settings.KAFKA_TOPIC_TOOL_PLAN_REQUEST,
            "groupId": settings.CORE_KAFKA_TOOL_PLAN_CONSUMER_GROUP_ID,
            "error": None,
        },
        "toolBuild": {
            "enabled": settings.CORE_KAFKA_CONSUMER_ENABLED,
            "started": False,
            "topic": settings.KAFKA_TOPIC_TOOL_BUILD_REQUEST,
            "groupId": settings.CORE_KAFKA_TOOL_BUILD_CONSUMER_GROUP_ID,
            "error": None,
        },
    }


def _mark_consumer_status(app: FastAPI, key: str, *, started: bool, error: Exception | None = None) -> None:
    status = app.state.core_consumer_status[key]
    status["started"] = started
    status["error"] = str(error) if error is not None else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Core database schema initialized.")

    app.state.sandbox_startup_status = {
        "enabled": settings.SANDBOX_STARTUP_CHECK,
        "checked": False,
        "ok": None,
        "error": None,
    }
    if settings.SANDBOX_STARTUP_CHECK:
        try:
            sandbox_info = await asyncio.to_thread(
                _sandbox_executor.verify_connectivity,
                pull_if_missing=settings.SANDBOX_PULL_ON_STARTUP,
            )
            app.state.sandbox_startup_status.update(
                {"checked": True, "ok": True, "error": None, "details": sandbox_info}
            )
            logger.info("Sandbox connectivity verified. image=%s status=%s host=%s",
                        sandbox_info["image"], sandbox_info["imageStatus"], sandbox_info["dockerHost"])
        except (SandboxStartupCheckError, SandboxUnavailableError) as exc:
            app.state.sandbox_startup_status.update(
                {"checked": True, "ok": False, "error": str(exc)}
            )
            if settings.SANDBOX_STARTUP_STRICT:
                raise
            logger.warning("Sandbox startup check failed: %s", exc)

    scheduler = setup_scheduler()
    app.state.billing_scheduler = scheduler
    app.state.tool_generation_consumer = None
    app.state.tool_plan_consumer = None
    app.state.tool_build_consumer = None
    app.state.core_consumer_status = _initial_consumer_status()

    if scheduler is not None:
        scheduler.start()
        logger.info(
            "Billing outbox scheduler started (interval=%ss, batch_size=%s)",
            settings.BILLING_OUTBOX_FLUSH_INTERVAL_SECONDS,
            settings.BILLING_OUTBOX_BATCH_SIZE,
        )
    else:
        logger.warning("Billing outbox scheduler is unavailable in this environment.")

    try:
        app.state.tool_generation_consumer = await start_tool_generation_consumer()
        _mark_consumer_status(
            app,
            "toolGeneration",
            started=app.state.tool_generation_consumer is not None,
        )
    except Exception as exc:
        _mark_consumer_status(app, "toolGeneration", started=False, error=exc)
        logger.error("Legacy ToolGeneration Kafka consumer startup failed: %s", exc, exc_info=True)

    try:
        app.state.tool_plan_consumer = await start_tool_plan_consumer()
        _mark_consumer_status(
            app,
            "toolPlan",
            started=app.state.tool_plan_consumer is not None,
        )
    except Exception as exc:
        _mark_consumer_status(app, "toolPlan", started=False, error=exc)
        logger.error("ToolPlan Kafka consumer startup failed: %s", exc, exc_info=True)

    try:
        app.state.tool_build_consumer = await start_tool_build_consumer()
        _mark_consumer_status(
            app,
            "toolBuild",
            started=app.state.tool_build_consumer is not None,
        )
    except Exception as exc:
        _mark_consumer_status(app, "toolBuild", started=False, error=exc)
        logger.error("Tool build Kafka consumer startup failed: %s", exc, exc_info=True)

    try:
        yield
    finally:
        if app.state.tool_build_consumer is not None:
            await app.state.tool_build_consumer.stop()
        if app.state.tool_plan_consumer is not None:
            await app.state.tool_plan_consumer.stop()
        if app.state.tool_generation_consumer is not None:
            await app.state.tool_generation_consumer.stop()
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Billing outbox scheduler stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Theseus B2B AI Agent Platform Core Server",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(health.router, tags=["System"])
app.include_router(stream.router, prefix="/api/v1", tags=["Streaming"])
app.include_router(plan.router, prefix="/api/v1", tags=["Plan"])
app.include_router(sandbox.router, prefix="/api/v1", tags=["Sandbox"])
app.include_router(remote_workspace.router, prefix="/api/v1", tags=["RemoteWorkspace"])

# 글로벌 예외 처리
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred."}
    )

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
