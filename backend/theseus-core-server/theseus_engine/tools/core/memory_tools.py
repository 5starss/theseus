"""Theseus 3단계 Agent Memory 도구들.

MemoryWriteTool  — 메모리 파일 작성 (user/project/local 스코프)
MemoryReadTool   — 메모리 파일 읽기
MemoryListTool   — 스코프별 메모리 목록 조회
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.memory.scoped_memory import MemoryScope, ScopedMemory


class MemoryWriteInput(BaseModel):
    scope: str = Field(default="local", description="메모리 스코프: 'user', 'project', 'local'")
    filename: str = Field(description="파일명 (.md 확장자 자동 추가)")
    content: str = Field(description="저장할 내용")


class MemoryWriteTool(BaseTool):
    name = "memory_write"
    description = (
        "에이전트 메모리를 파일로 저장합니다. "
        "scope: 'user'(전역), 'project'(프로젝트), 'local'(로컬전용). "
        "filename에 .md 확장자는 자동 추가됩니다."
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
                output=f"오류: scope은 'user', 'project', 'local' 중 하나여야 합니다. 입력: '{arguments.scope}'",
                is_error=True,
            )
        mem = ScopedMemory(cwd=context.cwd)
        path = mem.write(scope, arguments.filename, arguments.content)
        return ToolResult(output=f"저장됨: {path}")


class MemoryReadInput(BaseModel):
    scope: str = Field(default="local", description="메모리 스코프: 'user', 'project', 'local'")
    filename: str = Field(description="읽을 파일명")


class MemoryReadTool(BaseTool):
    name = "memory_read"
    description = (
        "저장된 에이전트 메모리 파일을 읽습니다. "
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
                output="오류: scope은 'user', 'project', 'local' 중 하나여야 합니다.",
                is_error=True,
            )
        mem = ScopedMemory(cwd=context.cwd)
        content = mem.read(scope, arguments.filename)
        if content is None:
            return ToolResult(
                output=f"'{arguments.scope}/{arguments.filename}' 파일이 존재하지 않습니다.",
                is_error=True,
            )
        return ToolResult(output=content)


class MemoryListInput(BaseModel):
    scope: str = Field(default="all", description="메모리 스코프: 'user', 'project', 'local', 'all'")


class MemoryListTool(BaseTool):
    name = "memory_list"
    description = (
        "저장된 에이전트 메모리 목록을 조회합니다. "
        "scope: 'user', 'project', 'local', 'all'(기본값: 전체)."
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
                    output="오류: scope은 'user', 'project', 'local', 'all' 중 하나여야 합니다.",
                    is_error=True,
                )

        lines: list[str] = []
        for scope in scopes:
            files = mem.list_files(scope)
            lines.append(f"[{scope.value}] {len(files)}개 파일")
            for f in files:
                lines.append(f"  - {f}")

        return ToolResult(output="\n".join(lines) if lines else "메모리 파일이 없습니다.")
