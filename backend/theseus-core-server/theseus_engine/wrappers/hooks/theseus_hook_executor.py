"""Theseus Hook Executor: OpenHarness HookExecutor 래핑.

OpenHarness의 공식 HookExecutor를 상속하여,
PRE_TOOL_USE 이벤트 시 Theseus 전용 검증기(Execution/Query)를
자동으로 실행하는 래핑 클래스입니다.
"""

from __future__ import annotations

import logging
import time
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
from theseus_engine.observability.stats import SessionStats

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
        enable_dynamic_tools: bool = True,
        permission_prompt: Any | None = None,
    ) -> None:
        super().__init__(registry, context)
        self._active_registry = active_registry
        self._full_registry = full_registry
        self._enable_dynamic_tools = enable_dynamic_tools
        self._permission_prompt = permission_prompt
        self._retriever = (
            ToolRetriever(full_registry)
            if full_registry and enable_dynamic_tools
            else None
        )
        # 세션 내 "항상 허용" 캐시 — 한 번 승인된 파괴적 툴은 재확인 불필요
        self._always_allow: set[str] = set()

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
        stats = SessionStats.get()

        # 1단계: OpenHarness 공식 Hook 파이프라인 실행
        base_result = await super().execute(event, payload)

        # [Bugfix] AgentHook이 Markdown backtick으로 감싸진 JSON을 반환할 경우
        # OpenHarness 파서가 실패하여 blocked=True가 되는 문제를 휴리스틱하게 복구합니다.
        if base_result.blocked:
            repaired_results = []
            any_repaired = False
            for res in base_result.results:
                if res.blocked and ("ok\": true" in res.reason.lower() or "ok\": true" in res.output.lower()):
                    # Markdown backtick 제거 후 재검증 시도
                    raw_text = res.output or res.reason
                    import re as _re
                    clean_text = _re.sub(r'```(?:json)?\n?|\n?```', '', raw_text).strip().lower()
                    if clean_text == '{"ok": true}':
                        log.info("[TheseusHook] AgentHook의 Markdown 응답을 감지하여 차단을 해제합니다.")
                        repaired_results.append(
                            HookResult(
                                hook_type=res.hook_type,
                                success=True,
                                output=res.output,
                                blocked=False,
                                metadata={**res.metadata, "repaired": True}
                            )
                        )
                        any_repaired = True
                        continue
                repaired_results.append(res)
            
            if any_repaired:
                base_result = AggregatedHookResult(results=repaired_results)

        # 공식 Hook이 여전히 차단 상태이면 바로 반환
        if base_result.blocked:
            return base_result

        # 2단계: PRE_TOOL_USE일 때만 Theseus 검증기 실행
        if event == HookEvent.PRE_TOOL_USE:
            tool_name = payload.get("tool_name", "")
            tool_input = payload.get("tool_input", {})
            # 툴 타이머 시작
            stats.tool_start(tool_name)

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

            # HITL 검증기: is_destructive=True 툴에 대해 사용자 승인 요청
            hitl_result = await self._check_hitl(tool_name, tool_input, payload)
            if hitl_result is not None:
                extra_results.append(hitl_result)

            base_result = AggregatedHookResult(results=extra_results)

        # 3단계: POST_TOOL_USE — 타이머 종료 + 동적 도구 검색 및 주입
        if event == HookEvent.POST_TOOL_USE:
            post_tool_name = payload.get("tool_name", "")
            is_error = bool(payload.get("is_error", False))
            stats.tool_end(post_tool_name, is_error=is_error)

            if self._enable_dynamic_tools:
                await self._discover_and_inject_tools(payload)

        return base_result

    async def _check_hitl(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        payload: dict[str, Any],
    ) -> HookResult | None:
        """파괴적 툴(is_destructive=True) 실행 전 사용자 승인을 요청합니다.

        - 세션 내 "항상 허용(always)" 캐시에 있으면 즉시 통과합니다.
        - permission_prompt 콜백이 없으면 자동 허용합니다.
        - 응답이 'y'/'yes'/'1' → 허용, 'a'/'always' → 항상 허용, 그 외 → 차단
        """
        if tool_name in self._always_allow:
            return None

        # active_registry에서 툴의 is_destructive 플래그 확인
        tool = None
        if self._active_registry:
            tool = self._active_registry.get(tool_name)
        if tool is None and self._full_registry:
            tool = self._full_registry.get(tool_name)

        is_destructive = getattr(tool, "is_destructive", False)
        if not is_destructive:
            return None

        stats = SessionStats.get()
        stats.increment("hitl.prompt_count")

        # permission_prompt 콜백 획득 (payload 또는 context에서)
        permission_prompt = payload.get("permission_prompt") or self._permission_prompt
        
        # 콜백이 없거나 호출 가능하지 않으면(예: bool 타입) HITL 스킵하고 허용
        if permission_prompt is None or not callable(permission_prompt):
            return None

        # 입력값 요약 (민감 데이터 노출 방지: 최대 200자)
        input_summary = str(tool_input)[:200]
        prompt_msg = (
            f"\n[보안 확인] 파괴적 작업 실행 요청\n"
            f"  툴: {tool_name}\n"
            f"  입력: {input_summary}\n"
            f"허용하시겠습니까? [y=허용 / a=항상허용 / 그 외=거부]: "
        )

        try:
            # OpenHarness PermissionPrompt 규격에 맞춰 (tool_name, reason) 형식으로 호출
            # 'ask_permission'이 bool을 반환할 수도 있고, 'input'처럼 문자열을 반환할 수도 있음
            result = await permission_prompt(tool_name, prompt_msg)
            
            if isinstance(result, bool):
                if result:
                    # '항상 허용'은 bool 인터페이스에서는 지원하지 않음 (단일 세션 허용)
                    return None
                else:
                    stats.increment("hitl.blocked_count")
                    return HookResult(
                        hook_type="theseus_hitl",
                        success=False,
                        blocked=True,
                        reason="User denied tool execution via boolean prompt.",
                    )
            
            # 문자열 반환 처리 (TUI/CLI input 등)
            response = str(result).strip().lower()
        except Exception as e:
            log.warning("[HITL] permission_prompt 호출 실패: %s → 차단", e)
            return HookResult(
                hook_type="theseus_hitl",
                success=False,
                blocked=True,
                reason=f"HITL 프롬프트 호출 실패로 차단: {e}",
            )

        if response in ("a", "always"):
            self._always_allow.add(tool_name)
            stats.increment("hitl.always_allow_count")
            log.info("[HITL] '%s' → 세션 내 항상 허용으로 등록됨", tool_name)
            return None

        if response in ("y", "yes", "1"):
            log.info("[HITL] '%s' → 사용자가 허용함", tool_name)
            return None

        log.info("[HITL] '%s' → 사용자가 거부함 (응답: '%s')", tool_name, response)
        stats.increment("hitl.blocked_count")
        return HookResult(
            hook_type="theseus_hitl",
            success=False,
            blocked=True,
            reason=f"사용자가 '{tool_name}' 실행을 거부했습니다.",
        )

    async def _discover_and_inject_tools(self, payload: dict[str, Any]) -> None:
        """도구 실행 결과를 바탕으로 새로운 연관 도구를 찾아 레지스트리에 주입합니다."""
        if not self._active_registry or not self._retriever or not self._full_registry:
            return

        tool_output = str(payload.get("tool_output", ""))
        if not tool_output or len(tool_output) < 5:
            return

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        search_query = self._build_injection_query(tool_name, tool_input, tool_output)

        try:
            new_tools = self._retriever.retrieve_top_k(
                search_query,
                self._full_registry,
                k=3,
                adaptive=False,
            )

            injected_count = 0
            for tool in new_tools:
                if self._active_registry.get(tool.name) is None:
                    self._active_registry.register(tool)
                    injected_count += 1
                    log.info(
                        "[DynamicDiscovery] 새로운 도구 '%s'를 주입했습니다. (쿼리: '%s')",
                        tool.name, search_query,
                    )

            if injected_count > 0:
                log.info(
                    "[DynamicDiscovery] 총 %d개의 도구가 현재 세션에 추가되었습니다.",
                    injected_count,
                )
        except Exception as e:
            log.debug("[DynamicDiscovery] 도구 검색 중 오류 발생: %s", e)

    @staticmethod
    def _build_injection_query(
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> str:
        """툴 실행 컨텍스트에서 의미있는 시맨틱 검색 쿼리를 생성합니다.

        tool_output 원문 대신 (툴 이름 + 입력 키 + 출력 신호)를 조합하여
        노이즈를 줄이고 검색 정확도를 높입니다.
        """
        import re as _re

        parts: list[str] = [tool_name]

        # 입력 키 추출 (값 제외 — 민감 정보 노출 방지)
        input_keys = list(tool_input.keys())[:3]
        parts.extend(input_keys)

        # 출력에서 파일 확장자 신호 추출
        extensions = _re.findall(
            r'\.(py|ts|js|tsx|jsx|json|yaml|yml|toml|md|sh|sql)\b',
            tool_output,
        )
        if extensions:
            parts.extend(list(dict.fromkeys(extensions))[:2])  # 중복 제거, 최대 2개

        # 출력에서 에러/상태 신호 추출
        output_lower = tool_output.lower()
        if any(w in output_lower for w in ("error", "exception", "traceback", "failed")):
            parts.append("error handling")
        if any(w in output_lower for w in ("not found", "no such file", "missing")):
            parts.append("file search")
        if any(w in output_lower for w in ("permission denied", "access denied")):
            parts.append("permission")
        if any(w in output_lower for w in ("timeout", "timed out")):
            parts.append("timeout retry")

        query = " ".join(parts)
        log.debug("[DynamicDiscovery] 생성된 주입 쿼리: '%s'", query)
        return query

