"""Theseus Hook Executor.

외부 HookExecutor를 상속하지 않고, 동일한 ``execute(event, payload)``
인터페이스를 독자적으로 구현합니다.  QueryEngine은 duck-typing으로 이
인터페이스를 호출하므로 상속이 필요하지 않습니다.

Theseus 검증기(Execution/Query), 감사 LLM, HITL, 동적 도구 검색을
모두 자체적으로 관리하며, 외부 hook 파이프라인이 선행하는
문제를 원천 제거합니다.
"""

from __future__ import annotations

import difflib
import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


# ---------------------------------------------------------------------------
# Theseus-native hook types
# ---------------------------------------------------------------------------
# QueryEngine 호환을 위해 동일한 필드/프로퍼티 시그니처를 유지합니다.


class HookEvent(str, Enum):
    """Theseus-native hook event types."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_COMPACT = "pre_compact"
    POST_COMPACT = "post_compact"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    NOTIFICATION = "notification"
    STOP = "stop"
    SUBAGENT_STOP = "subagent_stop"


@dataclass(frozen=True)
class HookResult:
    """Result from a single hook execution."""
    hook_type: str
    success: bool
    output: str = ""
    blocked: bool = False
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedHookResult:
    """Aggregated result for a hook event."""
    results: list[HookResult] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(r.blocked for r in self.results)

    @property
    def reason(self) -> str:
        for r in self.results:
            if r.blocked:
                return r.reason or r.output
        return ""


class TheseusHookExecutor:
    """Theseus 독립 Hook Executor.

    외부 HookExecutor를 상속하지 않으며, QueryEngine이
    duck-typing으로 호출하는 ``execute(event, payload)`` 인터페이스만
    구현합니다.  모든 검증(Execution/Query/Audit LLM/HITL)을
    Theseus가 직접 제어합니다.
    """

    _AUDIT_PROMPT = (
        "You are a security auditor. Does this file modification look safe, "
        "non-destructive, and not malicious? "
        "Return strict JSON: {{\"ok\": true}} or {{\"ok\": false, \"reason\": \"...\"}}. "
        "IMPORTANT: DO NOT use markdown backticks or any other formatting. "
        "Output raw JSON only. Arguments: {arguments}"
    )

    def __init__(
        self,
        *,
        active_registry: Any | None = None,
        full_registry: Any | None = None,
        enable_dynamic_tools: bool = True,
        permission_prompt: Any | None = None,
        llm_client: Any | None = None,
        audit_tools: set[str] | None = None,
    ) -> None:
        self._active_registry = active_registry
        self._full_registry = full_registry
        self._enable_dynamic_tools = enable_dynamic_tools
        self._permission_prompt = permission_prompt
        self._llm_client = llm_client
        self._audit_tools: set[str] = audit_tools or {
            "write_file",
            "edit_file",
            "local_write_report",
        }
        self._retriever = (
            ToolRetriever(full_registry)
            if full_registry and enable_dynamic_tools
            else None
        )
        self._always_allow: set[str] = set()
        self._last_failed_call: tuple[str, str] | None = None

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
        """Theseus 독립 Hook 파이프라인을 실행합니다.

        외부 HookExecutor를 호출하지 않으며, Theseus 자체
        검증기(Execution/Query/Audit LLM/HITL)만 사용합니다.

        Args:
            event: Hook 이벤트 종류 (Theseus-native HookEvent).
            payload: 이벤트 페이로드 (tool_name, tool_input 등).

        Returns:
            Theseus 검증기 결과를 합산한 AggregatedHookResult.
        """
        stats = SessionStats.get()

        # PRE_TOOL_USE 단계에서 중복 실패 호출 원천 차단
        if event == HookEvent.PRE_TOOL_USE:
            tool_name = payload.get("tool_name", "")
            tool_input_str = str(payload.get("tool_input", {}))

            if self._last_failed_call == (tool_name, tool_input_str):
                log.warning("[LoopBreaker] 동일한 실패 호출 반복 감지 차단: %s", tool_name)
                return AggregatedHookResult(
                    results=[
                        HookResult(
                            hook_type="theseus_loop_breaker",
                            success=False,
                            blocked=True,
                            reason=(
                                f"SYSTEM BLOCK: You just tried the EXACT SAME tool call "
                                f"({tool_name}) that previously failed. Stop repeating yourself! "
                                f"Change your arguments, write a Python script file instead of running inline commands, "
                                f"or explicitly ask the user for help."
                            )
                        )
                    ]
                )

        # 기본 결과 — 이벤트가 PRE/POST에 해당하지 않으면 빈 결과 반환
        result = AggregatedHookResult()

        # PRE_TOOL_USE — Theseus 검증기 실행
        if event == HookEvent.PRE_TOOL_USE:
            tool_name = payload.get("tool_name", "")
            tool_input = payload.get("tool_input", {})
            # 툴 타이머 시작
            stats.tool_start(tool_name)

            extra_results: list[HookResult] = []

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

            # 자체 감사 LLM — TheseusLLMClient로 직접 실행
            if tool_name in self._audit_tools:
                audit_result = await self._run_audit_llm(tool_name, tool_input)
                if audit_result is not None:
                    extra_results.append(audit_result)
                    # 감사 차단 시 HITL 건너뜀
                    if audit_result.blocked:
                        return AggregatedHookResult(results=extra_results)

            # HITL 검증기: is_destructive=True 툴에 대해 사용자 승인 요청
            hitl_result = await self._check_hitl(tool_name, tool_input, payload)
            if hitl_result is not None:
                extra_results.append(hitl_result)

            result = AggregatedHookResult(results=extra_results)

        # POST_TOOL_USE — 타이머 종료 + 동적 도구 검색 및 주입 — 타이머 종료 + 동적 도구 검색 및 주입
        if event == HookEvent.POST_TOOL_USE:
            post_tool_name = payload.get("tool_name", "")
            is_error = bool(payload.get("is_error", False))
            stats.tool_end(post_tool_name, is_error=is_error)

            # [추가 2] 에러 여부 기록 (무한 루프 방지용)
            tool_result = payload.get("tool_result")
            result_is_error = False
            if is_error:
                result_is_error = True
            elif tool_result and getattr(tool_result, "is_error", False):
                result_is_error = True
                
            if result_is_error:
                tool_input_str = str(payload.get("tool_input", {}))
                self._last_failed_call = (post_tool_name, tool_input_str)
            else:
                self._last_failed_call = None


            if self._enable_dynamic_tools:
                await self._discover_and_inject_tools(payload)

            # 도구 출력값 형식 보정 (dict/list -> JSON string)
            # Pydantic validation error (string_type) 방지
            # 주의: 이미 문자열인 경우는 건드리지 않아 이중 직렬화를 방지
            raw_output = payload.get("tool_output")
            if isinstance(raw_output, (dict, list)):
                try:
                    import json
                    payload["tool_output"] = json.dumps(raw_output, ensure_ascii=False, indent=2)
                except Exception:
                    payload["tool_output"] = str(raw_output)

            # Self-Reflection: .py 파일 수정 후 즉시 구문 검증
            if post_tool_name in ("write_file", "edit_file"):
                tool_input = payload.get("tool_input", {})
                file_path = tool_input.get("path") or tool_input.get("file_path") or ""
                if file_path.endswith(".py"):
                    self._validate_python_syntax(
                        file_path, payload
                    )

        return result

    async def _run_audit_llm(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> HookResult | None:
        """TheseusLLMClient를 직접 호출하여 파일 수정 안전성을 감사합니다.

        외부 hook 정의 없이 독립적으로 동작합니다.
        Returns:
            HookResult(blocked=True) if unsafe, None if safe or llm_client absent.
        """
        if self._llm_client is None:
            return None

        import json as _json

        try:
            args_str = _json.dumps(tool_input, ensure_ascii=False)[:2000]
            prompt = self._AUDIT_PROMPT.format(arguments=args_str)

            response = await self._call_audit_model(prompt)
            raw = self._extract_audit_text(response)

            # Markdown 펜스 제거
            import re as _re
            raw = _re.sub(r'```(?:json)?\n?|\n?```', '', raw).strip()

            parsed = _json.loads(raw)
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                parsed = parsed[0]
            if not isinstance(parsed, dict):
                raise ValueError(f"Audit LLM returned non-object JSON: {type(parsed).__name__}")
            if parsed.get("ok") is True:
                log.info("[AuditLLM] %s → 안전 확인", tool_name)
                return None

            reason = parsed.get("reason", "LLM 감사: 안전하지 않은 파일 수정 감지")
            log.warning("[AuditLLM] %s → 차단: %s", tool_name, reason)
            return HookResult(
                hook_type="theseus_audit_llm",
                success=False,
                blocked=True,
                reason=reason,
            )

        except Exception as e:
            log.warning(
                "[AuditLLM] 감사 LLM 호출 실패 — fail-closed 정책으로 차단 처리: %s", e
            )
            return HookResult(
                hook_type="theseus_audit_llm",
                success=False,
                blocked=True,
                reason=f"감사 LLM 호출 실패로 안전을 위해 실행을 차단했습니다: {e}",
            )

    async def _call_audit_model(self, prompt: str) -> Any:
        """Call either legacy generate() clients or the native stream API."""
        generate = getattr(self._llm_client, "generate", None)
        if callable(generate):
            return await generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=32768,
            )

        stream_message = getattr(self._llm_client, "stream_message", None)
        if not callable(stream_message):
            raise TypeError("Audit LLM client has neither generate() nor stream_message().")

        from theseus_engine.models.messages import ConversationMessage, TextBlock
        from theseus_engine.wrappers.llm_clients.api_types import (
            ApiMessageCompleteEvent,
            ApiMessageRequest,
            ApiTextDeltaEvent,
        )

        model_name = getattr(self._llm_client, "model_name", "audit")
        request = ApiMessageRequest(
            model=model_name,
            messages=[
                ConversationMessage(
                    role="user",
                    content=[TextBlock(text=prompt)],
                )
            ],
            max_tokens=32768,
            tools=[],
        )
        chunks: list[str] = []
        final_message: Any | None = None
        async for event in stream_message(request):
            if isinstance(event, ApiTextDeltaEvent):
                chunks.append(event.text)
            elif isinstance(event, ApiMessageCompleteEvent):
                final_message = event.message
        if final_message is not None:
            return final_message
        return "".join(chunks)

    def _extract_audit_text(self, value: Any) -> str:
        """Normalize provider-specific audit responses into text."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "".join(self._extract_audit_text(item) for item in value)
        if isinstance(value, dict):
            if "text" in value:
                return self._extract_audit_text(value["text"])
            if "content" in value:
                return self._extract_audit_text(value["content"])
            return ""

        content = getattr(value, "content", None)
        if content is not None:
            return self._extract_audit_text(content)
        text = getattr(value, "text", None)
        if text is not None:
            return self._extract_audit_text(text)
        return str(value)

    def _show_diff_preview(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> None:
        """write_file / edit_file 실행 전 변경 전후 diff를 rich로 터미널에 출력합니다.

        - write_file: 기존 파일 전체 vs 새 content 비교. 신규 파일이면 전체 추가로 표시.
        - edit_file: old_str vs new_str 인라인 비교.
        rich.Console이 터미널 환경(ANSI 지원 여부, Windows 인코딩)을 자동 감지합니다.
        """
        try:
            from rich.console import Console
            from rich.syntax import Syntax
            from rich.panel import Panel
        except ImportError:
            # rich 미설치 환경에서는 diff 미리보기 없이 HITL로 바로 진행
            return

        console = Console()

        try:
            if tool_name == "write_file":
                file_path = Path(tool_input.get("path", ""))
                new_content = tool_input.get("content", "")
                new_lines = new_content.splitlines(keepends=True)

                if file_path.exists():
                    old_lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
                    title = f"📄 파일 수정 미리보기: {file_path}"
                else:
                    old_lines = []
                    title = f"✨ 신규 파일 생성: {file_path}"

                diff_lines = list(difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"a/{file_path.name}",
                    tofile=f"b/{file_path.name}",
                    n=3,
                    lineterm="",
                ))

            elif tool_name == "edit_file":
                file_path = tool_input.get("path", "(알 수 없음)")
                old_str = tool_input.get("old_str", "")
                new_str = tool_input.get("new_str", "")
                title = f"✏️  파일 편집 미리보기: {file_path}"

                diff_lines = list(difflib.unified_diff(
                    old_str.splitlines(keepends=True),
                    new_str.splitlines(keepends=True),
                    fromfile="before",
                    tofile="after",
                    n=3,
                    lineterm="",
                ))
            else:
                return

            if not diff_lines:
                console.print(f"[yellow]  (변경 없음)[/yellow]")
                return

            # 최대 120줄만 표시
            truncated = len(diff_lines) > 120
            diff_str = "\n".join(diff_lines[:120])
            if truncated:
                diff_str += f"\n... (이하 {len(diff_lines) - 120}줄 생략)"

            syntax = Syntax(diff_str, "diff", theme="monokai", background_color="default")
            panel = Panel(
                syntax,
                title=f"[bold yellow]{title}[/bold yellow]",
                border_style="yellow",
                padding=(0, 1),
            )
            console.print(panel)

        except Exception as e:
            console.print(f"[yellow]  [diff 미리보기 실패: {e}][/yellow]")

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

        # 파일 수정 도구라면 diff 미리보기를 먼저 표시
        if tool_name in ("write_file", "edit_file"):
            self._show_diff_preview(tool_name, tool_input)

        # 입력값 요약 (민감 데이터 노출 방지: 최대 200자)
        input_summary = str(tool_input)[:200]
        action_label = "파일 수정" if tool_name in ("write_file", "edit_file") else "파괴적 작업"
        prompt_msg = (
            f"\n[보안 확인] {action_label} 실행 요청\n"
            f"  툴: {tool_name}\n"
            f"  입력: {input_summary}\n"
            f"허용하시겠습니까? [y=허용 / a=항상허용 / 그 외=거부]: "
        )

        try:
            # permission prompt callback은 (tool_name, reason) 형식으로 호출
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

    def _validate_python_syntax(
        self, file_path: str, payload: dict[str, Any]
    ) -> None:
        """수정된 Python 파일의 구문을 즉시 검증합니다 (Two-Tier).

        Tier 1: ``ast.parse()`` — 치명적 구문 에러 감지 (필수).
        Tier 2: ``ruff check`` — 미사용 import, 미선언 변수 등
                 의미론적 에러 감지 (ruff 설치 시에만).
        """
        import ast
        import shutil

        warnings: list[str] = []

        # --- Tier 1: ast.parse (필수) ---
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source, filename=file_path)
            log.info(
                "[SelfReflection] %s: 구문 검증 통과 (ast)", file_path
            )
        except SyntaxError as e:
            warnings.append(
                f"[SelfReflection] SYNTAX ERROR in {file_path}:\n"
                f"  Line {e.lineno}: {e.msg}\n"
                f"  이 에러를 반드시 수정하세요."
            )
        except Exception as e:
            log.debug(
                "[SelfReflection] 파일 읽기 실패: %s", e
            )
            return

        # --- Tier 2: ruff check (선택적) ---
        ruff_path = shutil.which("ruff")
        if ruff_path:
            try:
                import subprocess

                result = subprocess.run(
                    [ruff_path, "check", "--select=E,F", file_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.stdout.strip():
                    warnings.append(
                        f"[SelfReflection] LINT WARNINGS "
                        f"(ruff) for {file_path}:\n"
                        f"{result.stdout.strip()}\n"
                        f"  위 경고를 확인하고 필요시 수정하세요."
                    )
                    log.info(
                        "[SelfReflection] ruff 경고 %d건 발견",
                        result.stdout.count("\n"),
                    )
                else:
                    log.info(
                        "[SelfReflection] %s: ruff 검증 통과",
                        file_path,
                    )
            except Exception as e:
                log.debug("[SelfReflection] ruff 실행 실패: %s", e)

        # 경고가 있으면 tool_output에 추가하여 에이전트가 인지
        if warnings:
            combined = "\n".join(warnings)
            original = payload.get("tool_output", "")
            payload["tool_output"] = (
                f"{original}\n\n{combined}"
            )
            log.warning(combined)

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
            new_tools = await self._retriever.retrieve_top_k(
                search_query,
                self._full_registry,
                k=3,
                adaptive=False,
            )

            # 순회 중 레지스트리 변경(RuntimeError) 방지: 주입 대상을 먼저 확정한 뒤 일괄 등록
            to_inject = [
                tool for tool in new_tools
                if self._active_registry.get(tool.name) is None
            ]
            injected_count = 0
            for tool in to_inject:
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

