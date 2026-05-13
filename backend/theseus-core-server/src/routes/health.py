from fastapi import APIRouter, Request
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


@router.get("/health/details")
async def health_details(request: Request):
    consumer_status = getattr(request.app.state, "core_consumer_status", {})
    sandbox_startup_status = getattr(request.app.state, "sandbox_startup_status", None)
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "env": settings.ENV,
        "version": "0.1.0",
        "sandbox": {
            "image": settings.SANDBOX_IMAGE,
            "memoryLimit": settings.SANDBOX_MEMORY_LIMIT,
            "cpuQuota": settings.SANDBOX_CPU_QUOTA,
            "cpuPeriod": settings.SANDBOX_CPU_PERIOD,
            "keepFailedContainers": settings.SANDBOX_KEEP_FAILED_CONTAINERS,
            "startupCheck": settings.SANDBOX_STARTUP_CHECK,
            "startupStrict": settings.SANDBOX_STARTUP_STRICT,
            "pullOnStartup": settings.SANDBOX_PULL_ON_STARTUP,
            "dockerHost": settings.docker_host or "local-default",
            "hostTempRoot": settings.SANDBOX_HOST_TEMP_ROOT,
            "containerTempRoot": settings.SANDBOX_CONTAINER_TEMP_ROOT,
            "startupStatus": sandbox_startup_status,
        },
        "kafka": {
            "consumerEnabled": settings.CORE_KAFKA_CONSUMER_ENABLED,
            "bootstrapServers": settings.CORE_KAFKA_BOOTSTRAP_SERVERS,
            "topics": {
                "toolGenerationRequest": settings.KAFKA_TOPIC_TOOL_GENERATION_REQUEST,
                "toolRegenerationRequest": settings.KAFKA_TOPIC_TOOL_REGENERATION_REQUEST,
                "toolGenerationEvent": settings.KAFKA_TOPIC_TOOL_GENERATION_EVENT,
                "toolPlanRequest": settings.KAFKA_TOPIC_TOOL_PLAN_REQUEST,
                "toolPlanEvent": settings.KAFKA_TOPIC_TOOL_PLAN_EVENT,
                "toolBuildRequest": settings.KAFKA_TOPIC_TOOL_BUILD_REQUEST,
                "toolBuildEvent": settings.KAFKA_TOPIC_TOOL_BUILD_EVENT,
            },
            "groups": {
                "toolGeneration": settings.CORE_KAFKA_CONSUMER_GROUP_ID,
                "toolPlan": settings.CORE_KAFKA_TOOL_PLAN_CONSUMER_GROUP_ID,
                "toolBuild": settings.CORE_KAFKA_TOOL_BUILD_CONSUMER_GROUP_ID,
            },
            "consumers": consumer_status,
        },
        "database": {
            "host": settings.CORE_POSTGRES_HOST,
            "port": settings.CORE_POSTGRES_PORT,
            "database": settings.CORE_POSTGRES_DB,
            "schema": settings.CORE_POSTGRES_SCHEMA,
            "user": settings.CORE_POSTGRES_USER,
        },
    }
