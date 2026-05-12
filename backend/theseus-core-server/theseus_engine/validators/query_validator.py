"""Query Validator: 데이터베이스 쿼리 안전성 검증기.

에이전트가 실행하는 도구의 인자에 포함된 SQL 쿼리 문자열이
데이터를 파괴하거나 비인가된 변경을 수행하는지 검증합니다.

기본 모드: Regex (패턴 매칭, 비용 0)
고급 모드: LLM (에이전트 판단, THESEUS_USE_LLM_VALIDATOR=true)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Tuple

from theseus_engine.observability.tracer import (
    theseus_traceable,
)

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 위험 SQL 패턴 정의
# ------------------------------------------------------------------

# DDL (구조 변경) 패턴
_SQL_DDL_PATTERN = re.compile(
    r"\b(DROP\s+(TABLE|DATABASE|INDEX|VIEW|SCHEMA)"
    r"|ALTER\s+TABLE"
    r"|TRUNCATE\s+TABLE"
    r"|CREATE\s+(TABLE|DATABASE|INDEX))",
    re.IGNORECASE,
)

# DML (상태 변경) 패턴
_SQL_DML_PATTERN = re.compile(
    r"\b(INSERT\s+INTO"
    r"|UPDATE\s+\w+\s+SET"
    r"|DELETE\s+FROM)",
    re.IGNORECASE,
)

# WHERE 절 존재 여부 확인 (UPDATE/DELETE와 별도로 검사)
_SQL_WHERE_PATTERN = re.compile(r"\bWHERE\b", re.IGNORECASE)

# SQL 인젝션 의심 패턴
_SQL_INJECTION_PATTERN = re.compile(
    r"(;\s*(DROP|DELETE|INSERT|UPDATE|ALTER)"
    r"|--\s*$"
    r"|'\s*OR\s+'1'\s*=\s*'1"
    r"|UNION\s+SELECT)",
    re.IGNORECASE,
)


class QueryValidator:
    """도구 실행 인자에서 위험한 SQL 쿼리 패턴을 탐지합니다.

    기본(Default)은 Regex 패턴 매칭 방식이며,
    `THESEUS_USE_LLM_VALIDATOR=true` 환경변수가 설정되면
    LLM 기반 심층 분석 모드로 전환됩니다.
    """

    @theseus_traceable(
        run_type="tool",
        name="validate_query",
        tags=["validator", "query"],
    )
    @classmethod
    def validate(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """도구 실행 전 쿼리의 안전성을 검증합니다.

        Args:
            tool_name: 실행 대상 도구명.
            tool_input: 도구에 전달될 인자 딕셔너리.

        Returns:
            (안전 여부, 메시지) 튜플.
        """
        use_llm = (
            os.getenv("THESEUS_USE_LLM_VALIDATOR", "false")
            .lower() == "true"
        )

        if use_llm:
            return cls._validate_with_llm(
                tool_name, tool_input,
            )
        return cls._validate_with_regex(
            tool_name, tool_input,
        )

    # ------------------------------------------------------------------
    # Regex 기반 검증 (Default)
    # ------------------------------------------------------------------

    @classmethod
    def _validate_with_regex(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Regex 패턴 매칭으로 위험한 SQL 쿼리를 탐지."""
        warnings: List[str] = []
        serialized = str(tool_input)

        if _SQL_DDL_PATTERN.search(serialized):
            warnings.append(
                f"[Query] Tool '{tool_name}' arguments contain "
                f"DDL (schema-altering) queries (DROP/ALTER/TRUNCATE) detected."
            )

        if _SQL_INJECTION_PATTERN.search(serialized):
            warnings.append(
                f"[Query] Tool '{tool_name}' arguments contain "
                f"suspected SQL injection patterns detected."
            )

        if _SQL_DML_PATTERN.search(serialized):
            # UPDATE/DELETE에 WHERE 절이 없으면 대량 변경 위험 경고
            # 주의: _SQL_WHERE_PATTERN으로 전체 문자열에서 WHERE 존재 여부를 별도 확인
            if not _SQL_WHERE_PATTERN.search(serialized):
                warnings.append(
                    f"[Query] Tool '{tool_name}' arguments contain "
                    f"UPDATE/DELETE without a WHERE clause detected. "
                    f"(Risk of mass data modification)"
                )

        if warnings:
            detail = "\n".join(f"  - {w}" for w in warnings)
            log.warning(
                "Query validation warning (%d items):\n%s",
                len(warnings), detail,
            )
            return False, (
                f"Query validation warning "
                f"({len(warnings)} items):\n" + detail
            )

        return True, "Query validation passed."

    # ------------------------------------------------------------------
    # LLM 기반 검증 (Toggle)
    # ------------------------------------------------------------------

    @classmethod
    def _validate_with_llm(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """LLM을 활용한 SQL 쿼리 심층 안전성 분석.

        Note:
            이 메서드는 현재 뼈대(Stub)만 구현되어 있습니다.
            향후 TheseusLLMClient와 연동하여 실제 LLM 호출로
            대체할 예정입니다.
        """
        log.warning(
            "[LLM Validator] THESEUS_USE_LLM_VALIDATOR=true 이지만 "
            "Query LLM 검증기가 아직 구현되지 않았습니다. "
            "도구 '%s'에 대해 Regex 검증으로 폴백합니다.",
            tool_name,
        )
        return cls._validate_with_regex(
            tool_name, tool_input,
        )
