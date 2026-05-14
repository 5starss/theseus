"""Analysis Validator: AST 기반 보안 정적 분석기.

tool_factory.py의 ToolValidator에서 보안 검사 로직을 독립 모듈로
분리·고도화한 검증기입니다. PRE_TOOL_USE 이벤트와 결합할 수 있도록
설계되었습니다.

주요 검증 항목:
  - 금지된 모듈 임포트 차단 (subprocess, shutil, ctypes 등)
  - 위험 함수 호출 차단 (eval, exec, os.system 등)
  - 파일 시스템 파괴 함수 차단 (os.remove, rmtree 등)
  - 네트워크 소켓 직접 접근 차단
"""

from __future__ import annotations

import ast
import logging
from typing import List, Set, Tuple

from theseus_engine.observability.tracer import (
    theseus_traceable,
)

log = logging.getLogger(__name__)


class AnalysisValidator:
    """AST 기반의 코드 보안 정적 분석 검증기.

    생성된 파이썬 코드 문자열을 받아, 시스템에 해를 끼칠 수
    있는 패턴(위험 모듈 임포트, 파괴적 함수 호출 등)을 탐지
    하고 차단합니다.

    Attributes:
        BANNED_MODULES: 임포트가 금지된 최상위 모듈 집합.
        BANNED_FUNCTIONS: 호출이 금지된 함수/속성명 집합.
        BANNED_DUNDERS: 차단 대상 던더(매직) 속성 집합.
    """

    # ------------------------------------------------------------------
    # 블랙리스트 정의
    # ------------------------------------------------------------------

    BANNED_MODULES: Set[str] = {
        "subprocess", "shutil", "socket", "ctypes",
        "multiprocessing", "signal", "pty", "resource",
        "pickle", "shelve", "tempfile", "webbrowser",
    }

    BANNED_FUNCTIONS: Set[str] = {
        # 프로세스 / 쉘 실행
        "system", "popen", "exec", "eval", "compile",
        "execfile", "__import__",
        # 파일 시스템 파괴
        "remove", "rmdir", "unlink", "rmtree",
        "makedirs", "rename", "replace",
        # 시스템 제어
        "chown", "chmod", "kill", "fork",
    }

    BANNED_DUNDERS: Set[str] = {
        "__subclasses__", "__bases__", "__globals__",
        "__builtins__", "__code__",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    @theseus_traceable(
        run_type="tool",
        name="validate_analysis",
        tags=["validator", "ast", "security"],
    )
    def validate(cls, code: str) -> Tuple[bool, str]:
        """코드 문자열에 대해 보안 정적 분석을 수행합니다.

        Args:
            code: 검증할 파이썬 코드 문자열.

        Returns:
            (통과 여부, 메시지) 튜플.
            통과 시 (True, "보안 정적 분석 통과"),
            실패 시 (False, 위반 내역 문자열).
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax Error: {e}"

        errors: List[str] = []
        cls._check_banned_imports(tree, errors)
        cls._check_banned_calls(tree, errors)
        cls._check_banned_dunders(tree, errors)

        if errors:
            detail = "\n".join(f"  - {e}" for e in errors)
            log.warning(
                "Security static analysis failed (%d violations):\n%s",
                len(errors), detail,
            )
            return False, (
                f"Security static analysis failed ({len(errors)} violations):\n"
                + detail
            )

        return True, "Security static analysis passed."

    # ------------------------------------------------------------------
    # 내부 검사 메서드
    # ------------------------------------------------------------------

    @classmethod
    def _check_banned_imports(
        cls, tree: ast.Module, errors: List[str],
    ) -> None:
        """금지된 모듈의 import / from ... import 패턴을 검사."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in cls.BANNED_MODULES:
                        errors.append(
                            f"Security policy violation: Module '{alias.name}' "
                            f"is not allowed. "
                            f"(Reason: system destruction risk)"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in cls.BANNED_MODULES:
                        errors.append(
                            f"Security policy violation: Imports from "
                            f"'{node.module}' module are not permitted. "
                            f"(Reason: system destruction risk)"
                        )

    @classmethod
    def _check_banned_calls(
        cls, tree: ast.Module, errors: List[str],
    ) -> None:
        """금지된 함수 호출(os.system, eval 등)을 검사."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in cls.BANNED_FUNCTIONS:
                errors.append(
                    f"Security policy violation: Function '{func_name}()' "
                    f"is not allowed. "
                    f"(Reason: system destruction or code injection risk)"
                )

    @classmethod
    def _check_banned_dunders(
        cls, tree: ast.Module, errors: List[str],
    ) -> None:
        """위험 던더 속성 접근(__subclasses__ 등)을 검사."""
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in cls.BANNED_DUNDERS
            ):
                errors.append(
                    f"Security policy violation: Access to '{node.attr}' "
                    f"attribute is not permitted. "
                    f"(Reason: sandbox escape risk)"
                )
