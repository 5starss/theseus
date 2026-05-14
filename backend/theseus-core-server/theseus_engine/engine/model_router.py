"""Smart Model Router — 태스크 유형에 따라 적절한 모델을 자동 선택.

``THESEUS_MODEL_ROUTING=true`` 환경 변수가 활성화되면,
단순 작업(파일 읽기, 검색)에는 저비용 모델을,
추론이 필요한 작업(코드 생성, 리팩토링)에는 고성능 모델을
자동으로 라우팅합니다.
"""

from __future__ import annotations

import os
import logging
import threading

log = logging.getLogger(__name__)

# 단순 작업용 도구 패턴 (빠르고 저렴한 모델로 라우팅)
FAST_TOOLS: frozenset[str] = frozenset({
    "read_file", "glob", "grep", "web_search", "web_fetch",
    "memory_read", "memory_list", "skill_read", "skill_list",
    "task_list", "task_get", "task_output", "tool_search",
    "list_mcp_resources", "read_mcp_resource",
    "search_knowledge_base", "brief",
})

# 추론 집약적 도구 패턴 (고성능 모델로 라우팅)
REASONING_TOOLS: frozenset[str] = frozenset({
    "write_file", "edit_file", "bash", "create_tool",
    "deep_research", "agent", "ingest_document",
})


class ModelRouter:
    """태스크 유형에 따라 적절한 LLM 모델을 선택하는 라우터.

    ``.env`` 설정 키:
        - ``THESEUS_MODEL_ROUTING``: ``true`` 시 라우팅 활성화.
        - ``THESEUS_MODEL_FAST``: 단순 작업용 모델.
        - ``THESEUS_MODEL_REASONING``: 추론 작업용 모델.
        - ``THESEUS_MODEL``: 기본 모델.
    """

    def __init__(self) -> None:
        self.enabled = (
            os.getenv("THESEUS_MODEL_ROUTING", "false").lower()
            == "true"
        )
        self.default_model = os.getenv("THESEUS_MODEL", "gpt-4o")
        self.fast_model = os.getenv(
            "THESEUS_MODEL_FAST", self.default_model
        )
        self.reasoning_model = os.getenv(
            "THESEUS_MODEL_REASONING", self.default_model
        )

        if self.enabled:
            log.info(
                "[ModelRouter] 활성화됨 | fast=%s | reasoning=%s",
                self.fast_model,
                self.reasoning_model,
            )

    def select_model(
        self,
        recent_tool_calls: list[str] | None = None,
        mode: str = "Agent",
    ) -> str:
        """현재 맥락에 적합한 모델을 반환합니다.

        Args:
            recent_tool_calls: 직전 턴에서 호출된 도구 이름 목록.
            mode: 현재 에이전트 모드 (``"Plan"``, ``"Agent"`` 등).

        Returns:
            선택된 모델 이름 문자열.
        """
        if not self.enabled:
            return self.default_model

        # Plan Drafting / Executing → 항상 Reasoning 모델
        if mode in ("Plan", "Coordinator"):
            return self.reasoning_model

        # 직전 턴에서 호출된 도구 기반 분류
        if recent_tool_calls:
            has_reasoning = any(
                t in REASONING_TOOLS for t in recent_tool_calls
            )
            if has_reasoning:
                return self.reasoning_model

            all_fast = all(
                t in FAST_TOOLS for t in recent_tool_calls
            )
            if all_fast:
                return self.fast_model

        return self.default_model

    def get_status(self) -> str:
        """현재 라우팅 설정 상태를 문자열로 반환합니다."""
        if not self.enabled:
            return (
                f"[ModelRouter] 비활성 | "
                f"기본 모델: {self.default_model}"
            )
        return (
            f"[ModelRouter] 활성 | "
            f"fast={self.fast_model} | "
            f"reasoning={self.reasoning_model}"
        )


# ── 싱글톤 접근자 ───────────────────────────────────────────────

_router: ModelRouter | None = None
_router_lock = threading.Lock()


def get_model_router() -> ModelRouter:
    """ModelRouter 싱글톤 인스턴스를 반환합니다."""
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = ModelRouter()
    return _router
