"""Theseus-native slash command registry — OpenHarness 의존 없음."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


@dataclass
class CommandResult:
    """슬래시 커맨드 핸들러의 반환값."""
    message: str = ""
    exit_app: bool = False


@dataclass
class SlashCommand:
    """등록된 슬래시 커맨드 정의."""
    name: str
    description: str
    handler: Callable[[str, Any], Awaitable[CommandResult]]


class CommandRegistry:
    """슬래시 커맨드를 등록·조회하는 레지스트리."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}
        self._canonical_names: list[str] = []

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd
        if cmd.name not in self._canonical_names:
            self._canonical_names.append(cmd.name)

    def get(self, name: str) -> Optional[SlashCommand]:
        return self._commands.get(name)

    def names(self) -> list[str]:
        return list(self._canonical_names)

    async def dispatch(self, name: str, args: str, context: Any = None) -> Optional[CommandResult]:
        cmd = self._commands.get(name)
        if cmd is None:
            return None
        return await cmd.handler(args, context)
