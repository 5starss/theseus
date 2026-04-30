"""Theseus Hook Executor: OpenHarness HookExecutor 래핑.

OpenHarness의 공식 HookExecutor를 상속하여,
PRE_TOOL_USE 이벤트 시 Theseus 전용 검증기(Execution/Query)를
자동으로 실행하는 래핑 클래스입니다.
"""

from __future__ import annotations

import logging
from typing import Any

from openharness.hooks.events import HookEvent
from openharness.hooks.executor import (
    HookExecutionContext,
    HookExecutor,
)
from openharness.hooks.loader import HookRegistry
from openharness.hooks.types import (
    AggregatedHookResult,
    HookResult,
)
from openharness.tools.base import ToolRegistry

from theseus_engine.validators.execution_validator import (
    ExecutionValidator,
)
from theseus_engine.validators.query_validator import (
    QueryValidator,
)
from theseus_engine.observability.tracer import (
    theseus_traceable,
)
from theseus_engine.core.tool_retriever import ToolRetriever

log = logging.getLogger(__name__)


class TheseusHookExecutor(HookExecutor):
    """OpenHarness HookExecutor를 래핑하여 Theseus 검증기를 주입.

    PRE_TOOL_USE 이벤트가 발생하면 부모 클래스의 공식 Hook
    파이프라인을 먼저 실행한 뒤, Theseus 전용 검증기
    (ExecutionValidator, QueryValidator)를 추가로 실행합니다.
    """

    def __init__(
        self,
        registry: HookRegistry,
        context: HookExecutionContext,
        active_registry: ToolRegistry | None = None,
        full_registry: ToolRegistry | None = None,
    ) -> None:
        super().__init__(registry, context)
        self._active_registry = active_registry
        self._full_registry = full_registry
        self._retriever = ToolRetriever(full_registry) if full_registry else None

    @theseus_traceable(
        run_type="chain",
        name="theseus_hook_pipeline",
        tags=["hook", "security"],
    )
    async def execute(
        self,
        event: HookEvent,
        payload: dict[str, Any],
    ) -> AggregatedHookResult:
        """OpenHarness Hook 실행 후 Theseus 검증기를 연쇄 실행.

        Args:
            event: Hook 이벤트 종류.
            payload: 이벤트 페이로드 (tool_name, tool_input 등).

        Returns:
            공식 Hook + Theseus 검증기 결과를 합산한
            AggregatedHookResult.
        """
        # 1단계: OpenHarness 공식 Hook 파이프라인 실행
        base_result = await super().execute(event, payload)

        # 공식 Hook이 이미 차단했으면 바로 반환
        if base_result.blocked:
            return base_result

        # 2단계: PRE_TOOL_USE일 때만 Theseus 검증기 실행
        if event == HookEvent.PRE_TOOL_USE:
            tool_name = payload.get("tool_name", "")
            tool_input = payload.get("tool_input", {})

            extra_results = list(base_result.results)

            # Execution 검증기
            exec_ok, exec_msg = ExecutionValidator.validate(
                tool_name, tool_input,
            )
            if not exec_ok:
                log.warning(
                    "[TheseusHook] Execution 검증 차단: %s",
                    exec_msg,
                )
                extra_results.append(
                    HookResult(
                        hook_type="theseus_execution_validator",
                        success=False,
                        blocked=True,
                        reason=exec_msg,
                    )
                )

            # Query 검증기
            query_ok, query_msg = QueryValidator.validate(
                tool_name, tool_input,
            )
            if not query_ok:
                log.warning(
                    "[TheseusHook] Query 검증 차단: %s",
                    query_msg,
                )
                extra_results.append(
                    HookResult(
                        hook_type="theseus_query_validator",
                        success=False,
                        blocked=True,
                        reason=query_msg,
                    )
                )
            base_result = AggregatedHookResult(results=extra_results)

        # 3단계: POST_TOOL_USE일 때 동적 도구 검색 및 주입
        if event == HookEvent.POST_TOOL_USE:
            await self._discover_and_inject_tools(payload)

        return base_result

    async def _discover_and_inject_tools(self, payload: dict[str, Any]) -> None:
        """도구 실행 결과를 바탕으로 새로운 연관 도구를 찾아 레지스트리에 주입합니다."""
        if not self._active_registry or not self._retriever or not self._full_registry:
            return

        tool_output = str(payload.get("tool_output", ""))
        if not tool_output or len(tool_output) < 5:
            return

        # 결과물에서 핵심 키워드 추출 (예: 파일 확장자, 에러 메시지 등)
        # 여기서는 단순화를 위해 결과물 자체를 쿼리로 사용
        search_query = tool_output[:500] # 너무 길면 잘라서 검색
        
        try:
            # 현재 히스토리 맥락 없이 결과물 자체만으로 가장 연관성 높은 도구 탐색
            new_tools = self._retriever.retrieve_top_k(
                search_query,
                self._full_registry,
                k=3, # 소량만 추가
                adaptive=False
            )
            
            injected_count = 0
            for tool in new_tools:
                if self._active_registry.get(tool.name) is None:
                    # 도구 수혈!
                    self._active_registry.register(tool)
                    injected_count += 1
                    log.info(
                        "[DynamicDiscovery] 결과물 분석을 통해 새로운 도구 '%s'를 발견하여 주입했습니다.",
                        tool.name
                    )
            
            if injected_count > 0:
                log.info(
                    "[DynamicDiscovery] 총 %d개의 도구가 현재 세션에 추가되었습니다.",
                    injected_count
                )
        except Exception as e:
            log.debug("[DynamicDiscovery] 도구 검색 중 오류 발생: %s", e)

