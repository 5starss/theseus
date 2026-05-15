"""Safety checks for text file editing tools."""

from __future__ import annotations

import ast
import difflib
import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import PurePath
from typing import Any, Iterable


class RiskLevel(str, Enum):
    """Coarse risk level for a target path."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


_CONFIG_NAMES = {
    "config.py",
    "settings.py",
    "application.yml",
    "application.yaml",
    "application.properties",
    "pyproject.toml",
    "requirements.txt",
}
_DEPLOY_NAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "jenkinsfile",
    "nginx.conf",
}
_SECRET_SEGMENTS = {
    ".ssh",
    ".aws",
    ".gnupg",
    ".docker",
    ".kube",
}
_SECURITY_SEGMENTS = {
    "auth",
    "security",
    "permission",
    "permissions",
    "secret",
    "secrets",
}
_SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".sh",
}
_DOC_SUFFIXES = {".md", ".txt", ".rst"}
_TEST_SEGMENTS = {"test", "tests", "__tests__", "spec", "specs"}


@dataclass
class EditSafetyReport:
    """Structured safety result for a proposed file update."""

    allowed: bool
    risk_level: str
    path_category: str
    operation: str
    path: str
    old_sha256: str
    new_sha256: str
    added_lines: int = 0
    deleted_lines: int = 0
    changed_imports: list[str] = field(default_factory=list)
    removed_symbols: list[str] = field(default_factory=list)
    removed_config_keys: list[str] = field(default_factory=list)
    syntax_ok: bool | None = None
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rolled_back: bool = False

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)

    def mark_rolled_back(self) -> "EditSafetyReport":
        self.rolled_back = True
        return self


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def classify_edit_path(path: str | PurePath) -> tuple[RiskLevel, str]:
    """Return a conservative risk classification for a file path."""

    path_text = str(path).replace("\\", "/").lower()
    pure_path = PurePath(path_text)
    name = pure_path.name
    parts = set(pure_path.parts)

    if name.startswith(".env") or parts & _SECRET_SEGMENTS:
        return RiskLevel.VERY_HIGH, "secret"
    if parts & _SECURITY_SEGMENTS:
        return RiskLevel.VERY_HIGH, "security"
    if name in _DEPLOY_NAMES or name.startswith("docker-compose"):
        return RiskLevel.VERY_HIGH, "deploy"
    if name in _CONFIG_NAMES or name.endswith((".yml", ".yaml", ".toml", ".properties")):
        return RiskLevel.HIGH, "config"
    if parts & _TEST_SEGMENTS:
        return RiskLevel.MEDIUM, "test"
    if pure_path.suffix in _SOURCE_SUFFIXES:
        return RiskLevel.MEDIUM, "source"
    if pure_path.suffix in _DOC_SUFFIXES:
        return RiskLevel.LOW, "docs"
    return RiskLevel.MEDIUM, "unknown"


def validate_text_update(
    *,
    path: str | PurePath,
    old_content: str,
    new_content: str,
    operation: str,
    expected_change: str = "modify",
    preserve_patterns: Iterable[str] = (),
) -> EditSafetyReport:
    """Validate a proposed text update before it is reported as successful."""

    risk_level, path_category = classify_edit_path(path)
    deleted_lines, added_lines = _count_line_changes(old_content, new_content)
    violations: list[str] = []
    warnings: list[str] = []

    normalized_expected = (expected_change or "modify").strip().lower()
    if normalized_expected == "add_only" and deleted_lines > 0:
        violations.append(
            "expected_change=add_only but the proposed edit deletes existing lines."
        )

    for pattern in preserve_patterns:
        value = str(pattern)
        if not value:
            continue
        if value in old_content and value not in new_content:
            violations.append(f"preserve pattern was removed: {value[:120]}")
            continue
        old_matching_lines = [
            line
            for line in old_content.splitlines()
            if value in line
        ]
        if old_matching_lines:
            new_lines = set(new_content.splitlines())
            removed_matching_lines = [
                line
                for line in old_matching_lines
                if line not in new_lines
            ]
            if removed_matching_lines:
                violations.append(
                    "preserve pattern changed existing line: "
                    f"{removed_matching_lines[0][:120]}"
                )

    changed_imports: list[str] = []
    removed_symbols: list[str] = []
    removed_config_keys: list[str] = []
    syntax_ok: bool | None = None

    if str(path).endswith(".py"):
        python_report = _validate_python_update(old_content, new_content)
        syntax_ok = python_report.syntax_ok
        changed_imports = python_report.changed_imports
        removed_symbols = python_report.removed_symbols
        removed_config_keys = python_report.removed_config_keys
        violations.extend(python_report.violations)
        warnings.extend(python_report.warnings)

        if risk_level in {RiskLevel.HIGH, RiskLevel.VERY_HIGH}:
            for item in changed_imports:
                violations.append(f"high-risk Python file removed import: {item}")
            for item in removed_symbols:
                violations.append(f"high-risk Python file removed symbol: {item}")
            for item in removed_config_keys:
                violations.append(f"high-risk Python file removed config key: {item}")
        elif changed_imports or removed_symbols:
            warnings.append(
                "Python structure changed: removed imports/symbols should be intentional."
            )

    if (
        risk_level in {RiskLevel.HIGH, RiskLevel.VERY_HIGH}
        and deleted_lines > 20
        and normalized_expected not in {"repair", "overwrite", "delete"}
    ):
        violations.append(
            "large deletion in a high-risk file requires explicit repair/overwrite intent."
        )

    return EditSafetyReport(
        allowed=not violations,
        risk_level=risk_level.value,
        path_category=path_category,
        operation=operation,
        path=str(path),
        old_sha256=content_sha256(old_content),
        new_sha256=content_sha256(new_content),
        added_lines=added_lines,
        deleted_lines=deleted_lines,
        changed_imports=changed_imports,
        removed_symbols=removed_symbols,
        removed_config_keys=removed_config_keys,
        syntax_ok=syntax_ok,
        violations=violations,
        warnings=warnings,
    )


def build_overwrite_rejected_report(
    *,
    path: str | PurePath,
    old_content: str,
    new_content: str,
    operation: str,
) -> EditSafetyReport:
    risk_level, path_category = classify_edit_path(path)
    deleted_lines, added_lines = _count_line_changes(old_content, new_content)
    return EditSafetyReport(
        allowed=False,
        risk_level=risk_level.value,
        path_category=path_category,
        operation=operation,
        path=str(path),
        old_sha256=content_sha256(old_content),
        new_sha256=content_sha256(new_content),
        added_lines=added_lines,
        deleted_lines=deleted_lines,
        violations=[
            "write_file cannot overwrite an existing file unless allow_overwrite=true "
            "and overwrite_reason explains an explicit full replacement or repair."
        ],
    )


def render_blocked_message(report: EditSafetyReport) -> str:
    lines = [
        "파일 수정 안전 검증에서 차단되었습니다.",
        f"- 대상: {report.path}",
        f"- 위험도: {report.risk_level} ({report.path_category})",
        f"- 삭제된 라인: {report.deleted_lines}",
        f"- 추가된 라인: {report.added_lines}",
    ]
    if report.rolled_back:
        lines.append("- rollback: 원본 내용으로 복구했습니다.")
    if report.violations:
        lines.append("- 차단 사유:")
        lines.extend(f"  - {item}" for item in report.violations)
    if report.warnings:
        lines.append("- 참고 경고:")
        lines.extend(f"  - {item}" for item in report.warnings)
    lines.append("다음 단계: 더 작은 edit_file 패치로 다시 시도하거나, 전체 교체가 필요하면 명시적인 사유를 포함해 요청하세요.")
    return "\n".join(lines)


def render_success_message(
    *,
    report: EditSafetyReport,
    action: str,
    detail: str,
) -> str:
    lines = [
        action,
        "",
        "안전 검증 결과:",
        f"- 대상: {report.path}",
        f"- 위험도: {report.risk_level} ({report.path_category})",
        f"- 삭제된 라인: {report.deleted_lines}",
        f"- 추가된 라인: {report.added_lines}",
        f"- Python 문법 검증: {_format_syntax(report.syntax_ok)}",
        f"- import 변경: {len(report.changed_imports)}건",
        f"- class/function 삭제: {len(report.removed_symbols)}건",
        f"- config key 삭제: {len(report.removed_config_keys)}건",
    ]
    if detail:
        lines.insert(1, detail)
    if report.warnings:
        lines.append("- 참고 경고:")
        lines.extend(f"  - {item}" for item in report.warnings)
    return "\n".join(lines)


def _format_syntax(value: bool | None) -> str:
    if value is True:
        return "통과"
    if value is False:
        return "실패"
    return "해당 없음"


def _count_line_changes(old_content: str, new_content: str) -> tuple[int, int]:
    diff = difflib.ndiff(
        old_content.splitlines(),
        new_content.splitlines(),
    )
    deleted = 0
    added = 0
    for line in diff:
        if line.startswith("- "):
            deleted += 1
        elif line.startswith("+ "):
            added += 1
    return deleted, added


@dataclass
class _PythonUpdateReport:
    syntax_ok: bool | None = None
    changed_imports: list[str] = field(default_factory=list)
    removed_symbols: list[str] = field(default_factory=list)
    removed_config_keys: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _validate_python_update(old_content: str, new_content: str) -> _PythonUpdateReport:
    report = _PythonUpdateReport()
    try:
        new_tree = ast.parse(new_content)
        report.syntax_ok = True
    except SyntaxError as exc:
        report.syntax_ok = False
        report.violations.append(
            f"Python syntax error at line {exc.lineno}: {exc.msg}"
        )
        return report

    try:
        old_tree = ast.parse(old_content) if old_content.strip() else ast.parse("")
    except SyntaxError:
        report.warnings.append("Old Python file had syntax errors; structural comparison skipped.")
        return report

    old_structure = _collect_python_structure(old_tree)
    new_structure = _collect_python_structure(new_tree)
    report.changed_imports = sorted(old_structure["imports"] - new_structure["imports"])
    report.removed_symbols = sorted(old_structure["symbols"] - new_structure["symbols"])
    report.removed_config_keys = sorted(
        old_structure["config_keys"] - new_structure["config_keys"]
    )
    return report


def _collect_python_structure(tree: ast.AST) -> dict[str, set[str]]:
    imports: set[str] = set()
    symbols: set[str] = set()
    config_keys: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.add(f"from {module} import {alias.name}")
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(node.name)

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    config_keys.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            config_keys.add(node.target.id)

    return {
        "imports": imports,
        "symbols": symbols,
        "config_keys": config_keys,
    }


def extract_preserve_patterns_from_text(text: str) -> list[str]:
    """Best-effort extraction for explicit Korean/English invariants."""

    patterns: list[str] = []
    for regex in (
        r"`([^`]+)`\s*(?:은|는)?\s*(?:바꾸지|변경하지)\s*말",
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:은|는)?\s*(?:바꾸지|변경하지)\s*말",
        r"([A-Za-z_][A-Za-z0-9_ .:-]{1,80})\s*(?:은|는)?\s*(?:바꾸지|변경하지)\s*말",
        r"do not (?:change|modify) [`\"]?([^`\"\n]+)[`\"]?",
    ):
        for match in re.finditer(regex, text, flags=re.IGNORECASE):
            value = match.group(1).strip()
            if value and value not in patterns:
                patterns.append(value)
    return patterns


def merge_preserve_patterns(
    explicit_patterns: Iterable[str],
    metadata: dict[str, Any] | None,
) -> list[str]:
    """Merge explicit tool invariants with best-effort invariants from user goals."""

    merged: list[str] = []
    for pattern in explicit_patterns:
        value = str(pattern).strip()
        if value and value not in merged:
            merged.append(value)

    state = metadata.get("task_focus_state") if isinstance(metadata, dict) else None
    if isinstance(state, dict):
        candidates: list[str] = []
        goal = state.get("goal")
        if isinstance(goal, str):
            candidates.append(goal)
        recent_goals = state.get("recent_goals")
        if isinstance(recent_goals, list):
            candidates.extend(str(item) for item in recent_goals if item)
        for text in candidates:
            for pattern in extract_preserve_patterns_from_text(text):
                if pattern and pattern not in merged:
                    merged.append(pattern)
    return merged
