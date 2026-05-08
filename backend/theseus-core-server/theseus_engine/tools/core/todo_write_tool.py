"""TODO list management tool for Theseus agent."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)


class TodoWriteInput(BaseModel):
    """Arguments for TODO writes."""

    item: str = Field(description="TODO item text")
    checked: bool = Field(
        default=False, description="Mark the item as done"
    )
    path: str = Field(
        default="TODO.md",
        description="Path to the TODO markdown file",
    )


class TodoWriteTool(BaseTool):
    """Add or update an item in a TODO markdown checklist."""

    name = "todo_write"
    description = (
        "Add a new TODO item or mark an existing one as done "
        "in a markdown checklist file (default: TODO.md)."
    )
    input_model = TodoWriteInput
    permission_level = 1

    async def execute(
        self, arguments: TodoWriteInput, context: ToolExecutionContext
    ) -> ToolResult:
        path = Path(context.cwd) / arguments.path
        existing = (
            path.read_text(encoding="utf-8") if path.exists() else "# TODO\n"
        )

        unchecked = f"- [ ] {arguments.item}"
        checked = f"- [x] {arguments.item}"
        target = checked if arguments.checked else unchecked

        if unchecked in existing and arguments.checked:
            updated = existing.replace(unchecked, checked, 1)
        elif target in existing:
            return ToolResult(output=f"No changes: {path}")
        else:
            updated = existing.rstrip() + f"\n{target}\n"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        return ToolResult(output=f"TODO updated: {path}")
