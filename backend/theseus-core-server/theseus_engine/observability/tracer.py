"""Theseus Tracer: Bypass 가능한 LangSmith 트레이싱 유틸리티.

API 키가 등록되어 있지 않거나 환경변수/config로 enable 설정을
하지 않을 경우, 모든 트레이싱 로직은 자동으로 bypass(no-op)
처리됩니다.

환경변수 설정 가이드:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=<your_langsmith_api_key>
    LANGCHAIN_PROJECT=Theseus-Core-Server  (선택)
    THESEUS_TRACING_ENABLED=true           (명시적 활성화)

강제 bypass:
    LANGCHAIN_TRACING_V2=false
"""

from __future__ import annotations

import functools
import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

log = logging.getLogger(__name__)

F = TypeVar("F")
FALSE_VALUES = {"0", "false", "no", "off"}

# ------------------------------------------------------------------
# 활성화 판단 로직
# ------------------------------------------------------------------

_tracing_enabled: Optional[bool] = None


def is_tracing_enabled() -> bool:
    """트레이싱 활성화 여부를 판단합니다.

    `LANGCHAIN_TRACING_V2=false`가 설정되면 우선적으로 bypass됩니다.
    그 외에는 다음 두 조건을 **모두** 충족해야 활성화됩니다:
    1. `LANGCHAIN_API_KEY` 환경변수가 비어있지 않을 것.
    2. `THESEUS_TRACING_ENABLED` 환경변수가 `true`일 것
       (기본값: false → 명시적 opt-in).

    Returns:
        트레이싱 활성화 여부 (bool).
    """
    global _tracing_enabled

    if _tracing_enabled is not None:
        return _tracing_enabled

    langchain_tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2")
    tracing_v2_disabled = (
        langchain_tracing_v2 is not None
        and langchain_tracing_v2.strip().lower() in FALSE_VALUES
    )
    api_key = os.getenv("LANGCHAIN_API_KEY", "").strip()
    explicit_enable = (
        os.getenv("THESEUS_TRACING_ENABLED", "false")
        .lower() == "true"
    )

    _tracing_enabled = (
        not tracing_v2_disabled and bool(api_key) and explicit_enable
    )

    if _tracing_enabled:
        log.info(
            "[Theseus Tracer] LangSmith 트레이싱 활성화됨. "
            "Project: %s",
            os.getenv(
                "LANGCHAIN_PROJECT", "Theseus-Core-Server"
            ),
        )
    else:
        log.debug(
            "[Theseus Tracer] LangSmith 트레이싱 비활성화. "
            "(LANGCHAIN_TRACING_V2=false, "
            "LANGCHAIN_API_KEY 미설정 또는 "
            "THESEUS_TRACING_ENABLED!=true)"
        )

    return _tracing_enabled


def reset_tracing_cache() -> None:
    """캐싱된 활성화 판단을 초기화합니다 (테스트용)."""
    global _tracing_enabled
    _tracing_enabled = None


# ------------------------------------------------------------------
# 조건부 @traceable 데코레이터
# ------------------------------------------------------------------


def theseus_traceable(
    *,
    run_type: str = "chain",
    name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """LangSmith @traceable의 조건부 래퍼.

    트레이싱이 비활성화된 환경에서는 원본 함수를 그대로
    반환합니다 (no-op). 활성화 시 langsmith.traceable을
    동적으로 임포트하여 적용합니다.

    Args:
        run_type: LangSmith Run 유형
                  ("chain", "tool", "llm" 등).
        name: 트레이스 표시명 (None이면 함수명 사용).
        tags: LangSmith Run에 부착할 태그 목록.
        metadata: LangSmith Run에 부착할 메타데이터 딕셔너리.

    Returns:
        데코레이터 함수.
    """

    def decorator(func: F) -> F:
        if not is_tracing_enabled():
            return func

        try:
            from langsmith import traceable
        except ImportError:
            log.warning(
                "[Theseus Tracer] langsmith 패키지가 "
                "설치되어 있지 않습니다. 트레이싱을 건너뜁니다."
            )
            return func

        descriptor_type: type[classmethod] | type[staticmethod] | None = None
        target: Any = func
        if isinstance(func, classmethod):
            descriptor_type = classmethod
            target = func.__func__
        elif isinstance(func, staticmethod):
            descriptor_type = staticmethod
            target = func.__func__

        trace_name = name or getattr(
            target, "__name__", target.__class__.__name__
        )
        trace_tags = list(tags or [])
        trace_metadata = dict(metadata or {})

        try:
            traced_func = traceable(
                run_type=run_type,
                name=trace_name,
                tags=trace_tags,
                metadata=trace_metadata,
            )(target)
        except Exception as e:
            log.warning(
                "[Theseus Tracer] LangSmith traceable 적용 실패: %s. "
                "트레이싱 없이 원본 호출을 유지합니다.",
                e,
            )
            return func

        @functools.wraps(target)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return traced_func(*args, **kwargs)

        if descriptor_type is classmethod:
            return classmethod(wrapper)  # type: ignore[return-value]
        if descriptor_type is staticmethod:
            return staticmethod(wrapper)  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator


# ------------------------------------------------------------------
# 런타임 메타데이터 주입 컨텍스트 매니저
# ------------------------------------------------------------------


@contextmanager
def tracing_context(
    *,
    tags: Optional[list[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """LangSmith tracing_context의 조건부 래퍼.

    트레이싱이 비활성화된 환경에서는 아무 동작도 하지 않는
    no-op 컨텍스트 매니저로 동작합니다.

    Args:
        tags: 세션 범위에서 추가할 태그 목록.
        metadata: 세션 범위에서 추가할 메타데이터.

    Yields:
        None.
    """
    if not is_tracing_enabled():
        yield
        return

    try:
        from langsmith.run_helpers import (
            tracing_context as ls_tracing_context,
        )
        with ls_tracing_context(
            tags=tags or [],
            metadata=metadata or {},
        ):
            yield
    except ImportError:
        log.warning(
            "[Theseus Tracer] langsmith 패키지가 "
            "설치되어 있지 않습니다."
        )
        yield
    except Exception as e:
        log.warning(
            "[Theseus Tracer] tracing_context 오류: %s", e,
        )
        yield
