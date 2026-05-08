"""Theseus-native TUI runtime — OpenHarness build_runtime/start_runtime/handle_line 대체.

OH 의존 없는 순수 Theseus 런타임 번들과 헬퍼 함수를 제공합니다.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.tui.commands import CommandRegistry

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """런타임 앱 상태 스냅샷."""
    model: str = "unknown"
    permission_mode: str = "full_auto"
    session: str = "default"

    def get(self) -> "AppState":
        return self

    def set(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class TheseusBundle:
    """TUI가 사용하는 런타임 번들.

    OH bundle 인터페이스와 호환 유지:
      - bundle.engine          → QueryEngine
      - bundle.tool_registry   → ToolRegistry
      - bundle.api_client      → TheseusLLMClient
      - bundle.commands        → CommandRegistry
      - bundle.app_state       → AppState
      - bundle.external_api_client → bool
    """
    engine: QueryEngine
    tool_registry: Any
    api_client: Any
    commands: CommandRegistry = field(default_factory=CommandRegistry)
    app_state: AppState = field(default_factory=AppState)
    external_api_client: bool = False
    _background_tasks: list[asyncio.Task] = field(default_factory=list, repr=False)


async def build_theseus_runtime(
    *,
    system_prompt: str,
    cwd: str | Path,
    model: str,
    max_turns: int = 30,
    api_client: Any,
    permission_prompt: Optional[Callable] = None,
    tool_registry: Any,
    permission_checker: Any,
    hook_executor: Any = None,
    project_tool_permissions: dict | None = None,
) -> TheseusBundle:
    """Theseus-native 런타임 번들을 생성합니다."""
    engine = QueryEngine(
        api_client=api_client,
        tool_registry=tool_registry,
        permission_checker=permission_checker,
        hook_executor=hook_executor,
        cwd=Path(cwd),
        model=model,
        system_prompt=system_prompt,
        max_turns=max_turns,
        permission_prompt=permission_prompt,
    )

    bundle = TheseusBundle(
        engine=engine,
        tool_registry=tool_registry,
        api_client=api_client,
    )
    bundle.app_state.model = model
    return bundle


async def start_theseus_runtime(bundle: TheseusBundle) -> None:
    """런타임 번들의 백그라운드 태스크를 시작합니다 (필요 시 확장)."""
    # 현재는 별도 백그라운드 태스크 없음; 확장 포인트 유지
    pass


async def handle_theseus_line(
    bundle: TheseusBundle,
    line: str,
    *,
    print_system: Callable,
    render_event: Callable,
    clear_output: Optional[Callable] = None,
) -> bool:
    """슬래시 커맨드 또는 내부 명령을 처리합니다.

    Returns:
        True  → 계속 실행
        False → 앱 종료 요청
    """
    stripped = line.strip()
    if not stripped.startswith("/"):
        return True

    parts = stripped.split(None, 1)
    cmd_name = parts[0][1:].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd_name in ("exit", "quit", "bye"):
        await print_system("Goodbye.")
        return False

    if cmd_name == "clear" and clear_output:
        await clear_output()
        return True

    result = await bundle.commands.dispatch(cmd_name, args)
    if result is None:
        await print_system(f"Unknown command: /{cmd_name}")
        return True

    if result.message:
        await print_system(result.message)
    return not result.exit_app
