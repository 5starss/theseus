import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.auth.schemas import SessionContext
from src.config import settings
from theseus_engine.state import AgentMode, TheseusStateMachine

logger = logging.getLogger(__name__)

READ_ONLY_TOOL_ALLOWLIST: tuple[str, ...] = (
    "read_file",
    "glob",
    "grep",
)


class EngineInitializationError(ImportError):
    """Raised when the Theseus engine cannot be assembled safely."""


@dataclass(slots=True)
class EngineAssembly:
    """Server-safe QueryEngine bundle for Phase 1 streaming."""

    engine: Any
    model_name: str
    allowed_tools: tuple[str, ...]
    assistant_text_delta_type: type
    tool_execution_started_type: type
    tool_execution_completed_type: type
    error_event_type: type


def _resolve_api_key() -> str:
    api_key = (
        settings.OPENAI_API_KEY
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise EngineInitializationError(
            "No LLM API key is configured. Set OPENAI_API_KEY or GEMINI_API_KEY."
        )
    return api_key


def _resolve_base_url(model_name: str) -> str | None:
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url and "gemini" in model_name.lower():
        return "https://generativelanguage.googleapis.com/v1beta/openai/"
    return base_url


def _build_read_only_registry(full_registry: Any, tool_registry_cls: type) -> tuple[Any, tuple[str, ...]]:
    filtered_registry = tool_registry_cls()
    available_tools: list[str] = []

    for tool in full_registry.list_tools():
        if tool.name not in READ_ONLY_TOOL_ALLOWLIST:
            continue
        filtered_registry.register(tool)
        available_tools.append(tool.name)

    missing_tools = sorted(set(READ_ONLY_TOOL_ALLOWLIST) - set(available_tools))
    if missing_tools:
        logger.warning(
            "Allowlisted OpenHarness tools are unavailable and will be skipped: %s",
            ", ".join(missing_tools),
        )

    if not available_tools:
        raise EngineInitializationError(
            "No allowlisted OpenHarness read-only tools are available."
        )

    return filtered_registry, tuple(available_tools)


def get_query_engine(session: SessionContext) -> EngineAssembly:
    """Assemble a server-safe Theseus QueryEngine for Phase 1 streaming."""

    try:
        from openharness.api.openai_client import OpenAICompatibleClient
        from openharness.config.settings import PermissionSettings
        from openharness.engine.query_engine import QueryEngine
        from openharness.engine.stream_events import (
            AssistantTextDelta,
            ErrorEvent,
            ToolExecutionCompleted,
            ToolExecutionStarted,
        )
        from openharness.tools import create_default_tool_registry
        from openharness.tools.base import ToolRegistry
        from theseus_engine.rbac import TheseusPermissionChecker
    except ImportError as exc:
        raise EngineInitializationError(
            "OpenHarness is not available in the current Python environment."
        ) from exc

    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    api_key = _resolve_api_key()
    base_url = _resolve_base_url(model_name)

    api_client = OpenAICompatibleClient(
        api_key=api_key,
        base_url=base_url,
    )

    full_registry = create_default_tool_registry()
    tool_registry, allowed_tools = _build_read_only_registry(
        full_registry,
        ToolRegistry,
    )

    tool_permissions = {tool_name: 1 for tool_name in allowed_tools}
    permission_checker = TheseusPermissionChecker(
        settings=PermissionSettings(),
        user_level=session.permission_level,
        tool_permissions=tool_permissions,
    )

    state_machine = TheseusStateMachine(initial_mode=AgentMode.AGENT)
    engine = QueryEngine(
        api_client=api_client,
        tool_registry=tool_registry,
        permission_checker=permission_checker,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=state_machine.get_system_prompt(),
        max_turns=30,
    )

    return EngineAssembly(
        engine=engine,
        model_name=model_name,
        allowed_tools=allowed_tools,
        assistant_text_delta_type=AssistantTextDelta,
        tool_execution_started_type=ToolExecutionStarted,
        tool_execution_completed_type=ToolExecutionCompleted,
        error_event_type=ErrorEvent,
    )
