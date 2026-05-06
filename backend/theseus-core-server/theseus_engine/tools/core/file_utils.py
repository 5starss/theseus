"""Common file utilities for Theseus tools."""

from pathlib import Path
from typing import Optional

import re as _re

_MARKDOWN_LINK_RE = _re.compile(r'\[([^\]]+)\]\([^)]+\)')


def _strip_markdown_links(text: str) -> str:
    """마크다운 링크 `[label](url)` 에서 label만 추출합니다."""
    return _MARKDOWN_LINK_RE.sub(r'\1', text)


def _resolve_path(base: Path, candidate: str) -> Path:
    """Safely resolve a path relative to the working directory.

    LLM이 마크다운 링크 형태([file.py](http://...))로 경로를 전달하는 경우를 방어합니다.
    """
    # 마크다운 링크 구문 제거 후 실제 파일명만 사용
    candidate = _strip_markdown_links(candidate).strip()
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

def _check_path_security(path: Path, cwd: Path) -> Optional[str]:
    """Verify that the path is within the project root (CWD)."""
    try:
        # Check if path is under CWD
        path.relative_to(cwd)
        return None
    except ValueError:
        return f"Security Violation: Path '{path}' is outside the workspace root '{cwd}'."
