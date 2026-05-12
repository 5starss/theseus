"""Theseus 3단계 Agent Memory 스코핑.

Claude Code 참고: ~/.claude/memory/ (user), .claude/memory/ (project, git-tracked),
.claude/memory-local/ (local, gitignored) 의 3계층 구조를 Theseus에 맞게 구현.

스코프:
  user    — ~/.theseus/memory/   (사용자 홈, 모든 프로젝트 공유)
  project — .theseus/memory/     (프로젝트 루트, git 추적)
  local   — .theseus/memory-local/ (프로젝트 루트, .gitignore에 포함)

파일 형식: 마크다운 (.md), UTF-8
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class MemoryScope(str, Enum):
    USER = "user"
    PROJECT = "project"
    LOCAL = "local"


class ScopedMemory:
    """3단계 스코프 메모리 관리자.

    read_context()로 세 스코프의 모든 메모리를 합산하여 시스템 프롬프트에 주입할
    컨텍스트 문자열을 반환합니다.
    """

    _SCOPE_DIRS: dict[MemoryScope, str] = {
        MemoryScope.LOCAL: ".theseus/memory-local",
        MemoryScope.PROJECT: ".theseus/memory",
        MemoryScope.USER: "",  # 동적으로 계산
    }

    def __init__(self, cwd: Optional[Path] = None) -> None:
        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._user_dir = Path(os.getenv("THESEUS_DATA_DIR", Path.home() / ".theseus")) / "memory"

    def _resolve_dir(self, scope: MemoryScope) -> Path:
        if scope == MemoryScope.USER:
            return self._user_dir
        rel = self._SCOPE_DIRS[scope]
        return self._cwd / rel

    def _safe_path(self, scope: MemoryScope, filename: str) -> Path:
        """스코프 디렉터리 내 안전한 경로를 반환합니다.

        경로 탈출 공격(../etc/passwd 등)을 방지합니다.
        """
        if not filename.endswith(".md"):
            filename += ".md"
        target_dir = self._resolve_dir(scope).resolve()
        resolved = (target_dir / filename).resolve()
        if not resolved.is_relative_to(target_dir):
            raise ValueError(
                f"[Memory] 경로 탈출 감지: '{filename}' → '{resolved}' "
                f"(허용 범위: '{target_dir}')"
            )
        return resolved

    def write(self, scope: MemoryScope, filename: str, content: str) -> Path:
        """지정 스코프에 메모리 파일을 씁니다."""
        path = self._safe_path(scope, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        log.info("[Memory] wrote %s/%s (%d chars)", scope.value, filename, len(content))
        return path

    def read(self, scope: MemoryScope, filename: str) -> Optional[str]:
        """지정 스코프에서 메모리 파일을 읽습니다. 없으면 None 반환."""
        path = self._safe_path(scope, filename)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def delete(self, scope: MemoryScope, filename: str) -> bool:
        """지정 스코프의 메모리 파일을 삭제합니다. 성공 여부 반환."""
        path = self._safe_path(scope, filename)
        if path.exists():
            path.unlink()
            log.info("[Memory] deleted %s/%s", scope.value, filename)
            return True
        return False

    def list_files(self, scope: MemoryScope) -> list[str]:
        """지정 스코프의 모든 메모리 파일명 목록을 반환합니다."""
        d = self._resolve_dir(scope)
        if not d.exists():
            return []
        return sorted(p.name for p in d.glob("*.md"))

    def read_context(self) -> str:
        """세 스코프의 모든 메모리를 읽어 시스템 프롬프트 주입용 문자열로 반환합니다.

        우선순위: local > project > user (낮은 스코프가 나중에 나타나 더 구체적)
        """
        sections: list[str] = []

        scope_labels = {
            MemoryScope.USER: "User Memory",
            MemoryScope.PROJECT: "Project Memory",
            MemoryScope.LOCAL: "Local Memory",
        }

        # user → project → local 순으로 읽어 sections에 추가
        for scope in (MemoryScope.USER, MemoryScope.PROJECT, MemoryScope.LOCAL):
            files = self.list_files(scope)
            if not files:
                continue
            parts: list[str] = [f"## {scope_labels[scope]}"]
            for fname in files:
                content = self.read(scope, fname)
                if content:
                    parts.append(f"### {fname}\n{content.strip()}")
            if len(parts) > 1:
                sections.append("\n".join(parts))

        if not sections:
            return ""

        return "# Agent Memory\n\n" + "\n\n".join(sections)

    def ensure_gitignore(self) -> None:
        """프로젝트 로컬 메모리 디렉터리를 .gitignore에 추가합니다."""
        gitignore = self._cwd / ".gitignore"
        entry = ".theseus/memory-local/"
        try:
            existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
            if entry not in existing:
                with gitignore.open("a", encoding="utf-8") as f:
                    f.write(f"\n# Theseus local memory (not shared)\n{entry}\n")
                log.info("[Memory] .gitignore에 %s 추가됨", entry)
        except OSError as e:
            log.warning("[Memory] .gitignore 업데이트 실패: %s", e)
