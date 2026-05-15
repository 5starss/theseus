"""Runtime environment prompt section."""

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone


_git_branch_cache: dict[str, str] = {}  # cwd → branch 캐시 (프로세스 수명 동안 유효)


def _get_git_branch(cwd: str) -> str:
    """Git 브랜치 정보를 캐시하여 반환합니다.

    매 시스템 프롬프트 생성 시 subprocess를 호출하면 async 이벤트 루프를
    블로킹하므로 프로세스 수명 단위로 결과를 캐싱합니다.
    """
    if cwd in _git_branch_cache:
        return _git_branch_cache[cwd]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=cwd, timeout=5,
            stdin=subprocess.DEVNULL,
        )
        branch = f"yes (branch: {result.stdout.strip()})" if result.returncode == 0 else "no"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        branch = "no"
    _git_branch_cache[cwd] = branch
    return branch


def _get_environment_section() -> str:
    """현재 런타임 환경 정보를 동적으로 생성합니다."""
    os_name = platform.system()
    os_version = platform.release()
    arch = platform.machine()
    shell = os.environ.get("SHELL") or os.environ.get("COMSPEC", "unknown")
    cwd = os.getcwd()
    python_version = platform.python_version()
    python_exec = sys.executable
    venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_DEFAULT_ENV")
    date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # Git 정보 탐지 (캐시 사용 — 매 턴 subprocess 호출 방지)
    git_info = _get_git_branch(cwd)

    lines = [
        "# Environment",
        f"- OS: {os_name} {os_version}",
        f"- Architecture: {arch}",
        f"- Shell: {shell}",
        f"- Working directory: {cwd}",
        f"- Date: {date}",
        f"- Python: {python_version}",
        f"- Python executable: {python_exec}",
    ]
    if venv:
        lines.append(f"- Virtual environment: {venv}")
    lines.append(f"- Git: {git_info}")

    return "\n".join(lines)


get_environment_section = _get_environment_section

__all__ = ["get_environment_section"]
