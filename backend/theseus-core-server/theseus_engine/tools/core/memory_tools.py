"""Theseus 3-scope Agent Memory tools.

MemoryWriteTool  — Write memory files (user/project/local scope)
MemoryReadTool   — Read memory files
MemoryListTool   — List memory files per scope
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.memory.scoped_memory import MemoryScope, ScopedMemory


class MemoryWriteInput(BaseModel):
    scope: str = Field(default="local", description="Memory scope: 'user', 'project', 'local'")
    filename: str = Field(description="Filename (.md extension added automatically)")
    content: str = Field(description="Content to save")


class MemoryWriteTool(BaseTool):
    name = "memory_write"
    description = (
        "Save agent memory to a file. "
        "scope: 'user' (global), 'project' (shared), 'local' (local-only). "
        "The .md extension is added automatically to the filename."
    )
    input_model = MemoryWriteInput
    is_destructive = False
    permission_level = 1

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(self, arguments: MemoryWriteInput, context: ToolExecutionContext) -> ToolResult:
        try:
            scope = MemoryScope(arguments.scope.lower())
        except ValueError:
            return ToolResult(
                output=f"Error: scope must be one of 'user', 'project', 'local'. Got: '{arguments.scope}'",
                is_error=True,
            )
        mem = ScopedMemory(cwd=context.cwd)
        path = mem.write(scope, arguments.filename, arguments.content)
        return ToolResult(output=f"Saved: {path}")


class MemoryReadInput(BaseModel):
    scope: str = Field(default="local", description="Memory scope: 'user', 'project', 'local'")
    filename: str = Field(description="Filename to read")


class MemoryReadTool(BaseTool):
    name = "memory_read"
    description = (
        "Read a saved agent memory file. "
        "scope: 'user', 'project', 'local'."
    )
    input_model = MemoryReadInput
    is_destructive = False
    permission_level = 1

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: MemoryReadInput, context: ToolExecutionContext) -> ToolResult:
        try:
            scope = MemoryScope(arguments.scope.lower())
        except ValueError:
            return ToolResult(
                output="Error: scope must be one of 'user', 'project', 'local'.",
                is_error=True,
            )
        mem = ScopedMemory(cwd=context.cwd)
        content = mem.read(scope, arguments.filename)
        if content is None:
            return ToolResult(
                output=f"File not found: '{arguments.scope}/{arguments.filename}'",
                is_error=True,
            )
        return ToolResult(output=content)


class MemoryListInput(BaseModel):
    scope: str = Field(default="all", description="Memory scope: 'user', 'project', 'local', 'all'")


class MemoryListTool(BaseTool):
    name = "memory_list"
    description = (
        "List saved agent memory files. "
        "scope: 'user', 'project', 'local', 'all' (default: all scopes)."
    )
    input_model = MemoryListInput
    is_destructive = False
    permission_level = 1

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: MemoryListInput, context: ToolExecutionContext) -> ToolResult:
        scope_str = arguments.scope.lower()
        mem = ScopedMemory(cwd=context.cwd)

        if scope_str == "all":
            scopes = list(MemoryScope)
        else:
            try:
                scopes = [MemoryScope(scope_str)]
            except ValueError:
                return ToolResult(
                    output="Error: scope must be one of 'user', 'project', 'local', 'all'.",
                    is_error=True,
                )

        lines: list[str] = []
        for scope in scopes:
            files = mem.list_files(scope)
            lines.append(f"[{scope.value}] {len(files)} files")
            for f in files:
                lines.append(f"  - {f}")

        return ToolResult(output="\n".join(lines) if lines else "No memory files found.")
