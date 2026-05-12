"""Git worktree management tools for Theseus."""

from __future__ import annotations

import asyncio
import subprocess
import re
import logging
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)


class EnterWorktreeInput(BaseModel):
    """Arguments for entering a worktree."""

    branch: str = Field(description="Target branch name for the worktree")
    path: Optional[str] = Field(default=None, description="Optional worktree path")
    create_branch: bool = Field(default=True, description="Whether to create a new branch")
    base_ref: str = Field(default="HEAD", description="Base ref when creating a new branch")


EnterWorktreeInput.model_rebuild()


class EnterWorktreeTool(BaseTool):
    """Create a git worktree to work on a separate branch safely."""

    name = "enter_worktree"
    description = (
        "Create a git worktree in a separate directory. This allows you to "
        "modify code on a different branch without affecting the current directory. "
        "Useful for sandboxed experimentation."
    )
    input_model = EnterWorktreeInput
    permission_level = 2

    async def execute(
        self, arguments: EnterWorktreeInput, context: ToolExecutionContext
    ) -> ToolResult:
        top_level = await _git_output(context.cwd, "rev-parse", "--show-toplevel")
        if top_level is None:
            return ToolResult(
                output="Not a Git repository or Git command failed.",
                is_error=True
            )

        repo_root = Path(top_level)
        worktree_path = _resolve_worktree_path(repo_root, arguments.branch, arguments.path)
        
        # Ensure parent directory exists
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = ["git", "worktree", "add"]
        if arguments.create_branch:
            cmd.extend(["-b", arguments.branch, str(worktree_path), arguments.base_ref])
        else:
            cmd.extend([str(worktree_path), arguments.branch])

        returncode, output = await _run_git(cmd, cwd=repo_root)
        if returncode != 0:
            return ToolResult(output=f"Worktree creation failed: {output}", is_error=True)
            
        return ToolResult(
            output=(
                f"✅ Worktree created\n"
                f"Path: {worktree_path}\n"
                f"Branch: {arguments.branch}\n\n"
                f"You can now safely modify code in this directory."
            )
        )


class ExitWorktreeInput(BaseModel):
    """Arguments for worktree removal."""

    path: str = Field(description="Worktree path to remove")


class ExitWorktreeTool(BaseTool):
    """Remove an existing git worktree."""

    name = "exit_worktree"
    description = "Remove a git worktree by its path and clean up the directory."
    input_model = ExitWorktreeInput
    permission_level = 2

    async def execute(
        self, arguments: ExitWorktreeInput, context: ToolExecutionContext
    ) -> ToolResult:
        path = Path(arguments.path).expanduser()
        if not path.is_absolute():
            path = (context.cwd / path).resolve()
            
        returncode, output = await _run_git(
            ["git", "worktree", "remove", "--force", str(path)],
            cwd=context.cwd,
        )
        if returncode != 0:
            return ToolResult(output=f"Worktree removal failed: {output}", is_error=True)
            
        return ToolResult(output=f"✅ Worktree removed: {path}")


async def _run_git(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """git 명령을 비동기로 실행하여 (returncode, output) 반환."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = (stdout or stderr).decode("utf-8", errors="replace").strip()
        return proc.returncode or 0, output or str(cmd[-1])
    except Exception as exc:
        return 1, str(exc)


async def _git_output(cwd: Path, *args: str) -> str | None:
    """git 명령 결과 문자열 반환, 실패 시 None."""
    returncode, output = await _run_git(["git", *args], cwd=cwd)
    return output if returncode == 0 else None


def _resolve_worktree_path(repo_root: Path, branch: str, path: str | None) -> Path:
    if path:
        resolved = Path(path).expanduser()
        if not resolved.is_absolute():
            resolved = repo_root / resolved
        return resolved.resolve()
    
    # Default path: .theseus/worktrees/<branch-slug>
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-") or "worktree"
    return (repo_root / ".theseus" / "worktrees" / slug).resolve()
