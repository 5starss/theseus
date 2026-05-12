"""Lightweight code intelligence tool using Jedi for Python workspaces.

Provides IDE-like capabilities:
- document_symbol: List all symbols (classes, functions) in a file
- workspace_symbol: Search for symbols across the workspace
- go_to_definition: Jump to where a symbol is defined
- find_references: Find all usages of a symbol
- hover: Get type and docstring info for a symbol
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from theseus_engine.tools.core.file_utils import _check_path_security, _resolve_path

log = logging.getLogger(__name__)

# Jedi lazy import — graceful fallback if not installed
_jedi = None

def _get_jedi():
    global _jedi
    if _jedi is None:
        try:
            import jedi
            _jedi = jedi
        except ImportError:
            pass
    return _jedi


class LspInput(BaseModel):
    """Arguments for code intelligence queries."""

    operation: Literal[
        "document_symbol",
        "workspace_symbol",
        "go_to_definition",
        "find_references",
        "hover",
    ] = Field(description="The code intelligence operation to perform")

    file_path: Optional[str] = Field(
        default=None,
        description="Path to the source file (required for all except workspace_symbol)",
    )
    line: Optional[int] = Field(
        default=None, ge=1,
        description="1-based line number for position-based lookups",
    )
    character: Optional[int] = Field(
        default=None, ge=0,
        description="0-based character offset on the line",
    )
    query: Optional[str] = Field(
        default=None,
        description="Symbol name or substring for workspace_symbol / go_to_definition",
    )

    @model_validator(mode="after")
    def check_required_fields(self) -> "LspInput":
        if self.operation == "workspace_symbol":
            if not self.query:
                raise ValueError("workspace_symbol requires a query parameter.")
            return self
        if not self.file_path:
            raise ValueError(f"{self.operation} requires a file_path parameter.")
        if self.operation == "document_symbol":
            return self
        # go_to_definition, find_references, hover → need position
        if self.line is None:
            raise ValueError(
                f"{self.operation} requires a line parameter."
            )
        return self


class LspTool(BaseTool):
    """Read-only code intelligence for Python source files using Jedi."""

    name = "lsp"
    description = (
        "Inspect Python code: list symbols in a file (document_symbol), "
        "search symbols across workspace (workspace_symbol), "
        "jump to definitions (go_to_definition), "
        "find all references (find_references), "
        "or get type/docstring info (hover). "
        "Requires 'jedi' pip package."
    )
    input_model = LspInput
    permission_level = 1

    async def execute(
        self, arguments: LspInput, context: ToolExecutionContext
    ) -> ToolResult:
        jedi = _get_jedi()
        if jedi is None:
            return ToolResult(
                output=(
                    "The 'jedi' package is not installed. "
                    "Run: pip install jedi"
                ),
                is_error=True,
            )

        root = context.cwd.resolve()

        try:
            if arguments.operation == "workspace_symbol":
                # rglob + read_text + jedi 분석은 동기 블로킹 — executor로 오프로드
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self._workspace_symbol, jedi, root, arguments.query or ""
                )

            file_path = _resolve_path(root, arguments.file_path or "")
            security_err = _check_path_security(file_path, root)
            if security_err:
                return ToolResult(output=security_err, is_error=True)
            if not file_path.exists():
                return ToolResult(output=f"File not found: {file_path}", is_error=True)
            if file_path.suffix != ".py":
                return ToolResult(output="Only Python (.py) files are currently supported.", is_error=True)

            source = file_path.read_text(encoding="utf-8", errors="replace")
            script = jedi.Script(source, path=str(file_path), project=jedi.Project(path=str(root)))

            if arguments.operation == "document_symbol":
                return self._document_symbol(script, file_path, root)
            elif arguments.operation == "go_to_definition":
                return self._go_to_definition(script, arguments, root)
            elif arguments.operation == "find_references":
                return self._find_references(script, arguments, root)
            elif arguments.operation == "hover":
                return self._hover(script, arguments, root)
            else:
                return ToolResult(output=f"Unknown operation: {arguments.operation}", is_error=True)
        except Exception as e:
            log.error("LSP operation failed: %s", e)
            return ToolResult(output=f"LSP error: {e}", is_error=True)

    # ── Operations ───────────────────────────────────────────────

    def _workspace_symbol(self, jedi, root: Path, query: str) -> ToolResult:
        """전체 프로젝트에서 심볼을 검색합니다."""
        project = jedi.Project(path=str(root))
        names = jedi.Script("", project=project).complete(1, 0)

        # Jedi의 search는 project.complete로는 부족하므로 
        # 파일을 순회하며 names를 수집합니다.
        results = []
        for py_file in root.rglob("*.py"):
            if any(p.startswith(".") for p in py_file.parts) or "__pycache__" in py_file.parts:
                continue
            try:
                src = py_file.read_text(encoding="utf-8", errors="ignore")
                script = jedi.Script(src, path=str(py_file), project=project)
                for name in script.get_names(all_scopes=False, definitions=True):
                    if query.lower() in name.name.lower():
                        rel = _rel_path(py_file, root)
                        results.append(f"{name.type:>10}  {name.name}  {rel}:{name.line}")
            except Exception:
                continue
            if len(results) >= 100:
                break

        if not results:
            return ToolResult(output=f"No symbols found matching '{query}'.")
        return ToolResult(output=f"Found {len(results)} symbols:\n" + "\n".join(results))

    def _document_symbol(self, script, file_path: Path, root: Path) -> ToolResult:
        """파일 내의 모든 심볼(클래스, 함수, 변수 등)을 나열합니다."""
        names = script.get_names(all_scopes=True, definitions=True)
        if not names:
            return ToolResult(output="(no symbols)")
        lines = []
        for n in names:
            indent = "  " * (n.get_line_code_position() if hasattr(n, 'get_line_code_position') else 0)
            lines.append(f"{n.type:>12}  {indent}{n.name}  (line {n.line})")
        rel = _rel_path(file_path, root)
        return ToolResult(output=f"Symbols in {rel}:\n" + "\n".join(lines))

    def _go_to_definition(self, script, args: LspInput, root: Path) -> ToolResult:
        """심볼의 정의 위치로 이동합니다."""
        col = (args.character or 0)
        defs = script.goto(args.line, col)
        if not defs:
            return ToolResult(output="Definition not found.")
        lines = []
        for d in defs:
            p = Path(d.module_path) if d.module_path else Path("(builtin)")
            lines.append(f"{d.type} {d.name} → {_rel_path(p, root)}:{d.line}:{d.column}")
            if d.docstring(fast=True):
                doc = d.docstring(fast=True).split("\n")[0]
                lines.append(f"  doc: {doc}")
        return ToolResult(output="\n".join(lines))

    def _find_references(self, script, args: LspInput, root: Path) -> ToolResult:
        """심볼의 모든 참조를 찾습니다."""
        col = (args.character or 0)
        refs = script.get_references(args.line, col)
        if not refs:
            return ToolResult(output="No references found.")
        lines = []
        for r in refs[:100]:
            p = Path(r.module_path) if r.module_path else Path("(unknown)")
            code = r.get_line_code().strip() if hasattr(r, 'get_line_code') else ""
            lines.append(f"{_rel_path(p, root)}:{r.line}:{r.column}  {code}")
        return ToolResult(
            output=f"Found {len(refs)} references:\n" + "\n".join(lines)
            + ("\n... (truncated)" if len(refs) > 100 else "")
        )

    def _hover(self, script, args: LspInput, root: Path) -> ToolResult:
        """심볼의 타입 정보와 독스트링을 반환합니다."""
        col = (args.character or 0)
        names = script.infer(args.line, col)
        if not names:
            return ToolResult(output="(no hover results)")
        parts = []
        for n in names[:5]:
            parts.append(f"Type: {n.type}  Name: {n.name}")
            if n.module_path:
                parts.append(f"  Path: {_rel_path(Path(n.module_path), root)}:{n.line}")
            doc = n.docstring(fast=True)
            if doc:
                # 첫 3줄만
                doc_lines = doc.strip().split("\n")[:3]
                parts.append(f"  Doc: {chr(10).join(doc_lines)}")
        return ToolResult(output="\n".join(parts))


# ── helpers ──────────────────────────────────────────────────────

def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
