"""Theseus LLM Client — Router / Facade for multi-provider support.

Selects the correct Theseus-native API client based on the model name
and delegates streaming to it.  Gemini-specific quirks (thought_signature
preservation) are handled by ``gemini_compat``.

모든 타입을 Theseus-native 모듈에서 import합니다.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import AsyncIterator, Any

from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageRequest,
    ApiStreamEvent,
    SupportsStreamingMessages,
    ApiTextDeltaEvent,
    ApiMessageCompleteEvent,
    AuthenticationFailure,
    UsageSnapshot,
)
from theseus_engine.wrappers.llm_clients.anthropic_client import TheseusAnthropicClient
from theseus_engine.wrappers.llm_clients.openai_compat_client import (
    TheseusOpenAICompatClient,
    _convert_messages_to_openai,
    _convert_tools_to_openai,
    _token_limit_param_for_model,
    _strip_think_blocks,
)
from theseus_engine.models.messages import (
    ConversationMessage, ContentBlock, TextBlock, ToolUseBlock,
)

from theseus_engine.wrappers.llm_clients.gemini_compat import (
    extract_extra_content,
    rebuild_tool_call_dict,
    patch_assistant_tool_calls,
)
from theseus_engine.engine.model_router import get_model_router

# --- DEBUG: Payload Dump Configuration ---
# ── Debug Dump 설정 ──────────────────────────────────────────────
# THESEUS_DEBUG_DUMP=true  → 덤프 활성화 (기본: 비활성)
# THESEUS_DEBUG_DUMP_DIR   → 저장 경로 오버라이드 (기본: ~/.theseus/debug_dumps)
_DEBUG_DUMP_ENABLED: bool = os.getenv("THESEUS_DEBUG_DUMP", "false").lower() == "true"
DEBUG_DUMP_DIR = Path(
    os.getenv("THESEUS_DEBUG_DUMP_DIR", Path.home() / ".theseus" / "debug_dumps")
)


def _sanitize_debug_path_part(value: Any, *, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        text = default
    text = re.sub(r"[^A-Za-z0-9._=-]+", "_", text).strip("._")
    return (text or default)[:120]


def _debug_scope_name(debug_context: dict[str, Any] | None) -> str:
    context = debug_context if isinstance(debug_context, dict) else {}
    explicit = context.get("debug_dump_scope")
    if explicit:
        return _sanitize_debug_path_part(explicit, default="session_unscoped")

    project_id = context.get("project_id")
    chat_session_id = context.get("chat_session_id")
    session_id = context.get("session_id")
    run_id = context.get("run_id")

    if project_id is not None and chat_session_id is not None:
        return _sanitize_debug_path_part(
            f"project_{project_id}_chat_{chat_session_id}",
            default="session_unscoped",
        )
    if session_id is not None:
        return _sanitize_debug_path_part(f"session_{session_id}", default="session_unscoped")
    if run_id is not None:
        return _sanitize_debug_path_part(f"run_{run_id}", default="session_unscoped")
    return "session_unscoped"


def _dump_debug_payload(
    name: str,
    data: Any,
    *,
    debug_context: dict[str, Any] | None = None,
) -> None:
    """페이로드를 JSON 파일로 덤프합니다.

    THESEUS_DEBUG_DUMP=true 일 때만 실행됩니다.
    저장 경로: THESEUS_DEBUG_DUMP_DIR/<session-scope>/<payload-name>.json
    """
    if not _DEBUG_DUMP_ENABLED:
        return
    try:
        scope_name = _debug_scope_name(debug_context)
        dump_dir = DEBUG_DUMP_DIR / scope_name
        dump_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{_sanitize_debug_path_part(name, default='payload')}.json"
        dump_path = dump_dir / file_name
        tmp_path = dump_path.with_name(f".{dump_path.stem}.{os.getpid()}.{id(data)}.tmp")

        def _serializer(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=_serializer)
        tmp_path.replace(dump_path)
        print(f"\n[DEBUG] Dumped {name} to {dump_path}\n", file=sys.stderr)
    except Exception as e:
        print(f"\n[DEBUG] Failed to dump {name}: {e}\n", file=sys.stderr)
# -----------------------------------------


def _required_api_key(provider: str, *env_names: str) -> str:
    placeholders: list[str] = []
    for env_name in env_names:
        value = os.getenv(env_name)
        if not value or not value.strip():
            continue
        candidate = value.strip()
        if _looks_like_placeholder_api_key(candidate):
            placeholders.append(env_name)
            continue
        return candidate
    expected = " or ".join(env_names)
    suffix = (
        f" Ignored placeholder values in {', '.join(placeholders)}."
        if placeholders
        else ""
    )
    raise AuthenticationFailure(
        f"{provider} API key is not configured. Set {expected} before starting Theseus."
        f"{suffix}"
    )


def _looks_like_placeholder_api_key(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    if normalized in {"", "test", "your-api-key", "your_api_key", "changeme"}:
        return True
    return any(
        marker in normalized
        for marker in (
            "your-openai-api-key",
            "your-anthropic-api-key",
            "your-gemini-api-key",
            "your-deepseek-api-key",
            "api-key-here",
            "sk-your-",
            "aizasy-your-",
        )
    )


class TheseusGeminiClient(TheseusOpenAICompatClient):
    """OpenAICompatibleClient that preserves Gemini's ``extra_content``
    (thought_signature) across multi-turn tool-calling conversations.
    """

    async def _stream_once(
        self, request: ApiMessageRequest
    ) -> AsyncIterator[ApiStreamEvent]:
        # 1. Convert messages and patch thought_signatures
        openai_messages = _convert_messages_to_openai(
            request.messages, request.system_prompt,
        )
        patch_assistant_tool_calls(openai_messages, request.messages)

        openai_tools = (
            _convert_tools_to_openai(request.tools) if request.tools else None
        )

        params: dict[str, Any] = {
            "model": request.model,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        params.update(
            _token_limit_param_for_model(request.model, request.max_tokens),
        )
        if openai_tools:
            params["tools"] = openai_tools
            params.pop("stream_options", None)

        # --- DEBUG: Dump final params sent to Gemini ---
        _dump_debug_payload(
            "gemini_final_params",
            params,
            debug_context=request.debug_context,
        )
        # -----------------------------------------------

        # 2. Stream and collect response
        collected_content = ""
        collected_reasoning = ""
        collected_tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage_data: dict[str, int] = {}
        _think_buf = ""

        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            if not chunk.choices:
                if chunk.usage:
                    usage_data = {
                        "input_tokens": chunk.usage.prompt_tokens or 0,
                        "output_tokens": chunk.usage.completion_tokens or 0,
                    }
                continue

            delta = chunk.choices[0].delta
            chunk_finish = chunk.choices[0].finish_reason

            if chunk_finish:
                finish_reason = chunk_finish

            reasoning_piece = getattr(delta, "reasoning_content", None) or ""
            if reasoning_piece:
                collected_reasoning += reasoning_piece

            if delta.content:
                _think_buf += delta.content
                visible, _think_buf = _strip_think_blocks(_think_buf)
                if visible:
                    collected_content += visible
                    yield ApiTextDeltaEvent(text=visible)

            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": getattr(tc_delta, "id", "") or "",
                            "name": "",
                            "arguments": "",
                            "extra_content": None,
                        }
                    entry = collected_tool_calls[idx]
                    if getattr(tc_delta, "id", None):
                        entry["id"] = tc_delta.id
                    if getattr(tc_delta, "function", None):
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

                    # Extract Gemini extra_content via compat module
                    ec = extract_extra_content(tc_delta)
                    if ec is not None:
                        entry["extra_content"] = ec

            if chunk.usage:
                usage_data = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }

        # 3. Build final ConversationMessage
        content: list[ContentBlock] = []
        if collected_content:
            content.append(TextBlock(text=collected_content))

        raw_tool_calls_dict: dict[str, dict[str, Any]] = {}
        for _idx in sorted(collected_tool_calls.keys()):
            tc = collected_tool_calls[_idx]
            if not tc["name"]:
                continue
            try:
                args = json.loads(tc["arguments"])
            except (json.JSONDecodeError, TypeError) as parse_err:
                # 빈 dict로 조용히 넘기지 않고 에이전트가 인지할 수 있도록 에러를 노출
                # ToolUseBlock은 남겨 히스토리 구조를 유지하되, input에 에러 정보를 담음
                args = {"_parse_error": str(parse_err), "_raw": tc["arguments"][:200]}
            content.append(ToolUseBlock(
                id=tc["id"], name=tc["name"], input=args,
            ))

            raw_tool_calls_dict[tc["id"]] = rebuild_tool_call_dict(
                tc_id=tc["id"],
                name=tc["name"],
                arguments=tc["arguments"],
                extra_content=tc["extra_content"],
            )

        final_message = ConversationMessage(role="assistant", content=content)
        if raw_tool_calls_dict:
            object.__setattr__(
                final_message, "_raw_tool_calls", raw_tool_calls_dict,
            )

        if collected_reasoning:
            object.__setattr__(final_message, "_reasoning", collected_reasoning)

        yield ApiMessageCompleteEvent(
            message=final_message,
            usage=UsageSnapshot(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            ),
            stop_reason=finish_reason,
        )


class TheseusLLMClient(SupportsStreamingMessages):
    """Router / Facade Client that selects the underlying API client
    based on the model name prefix or pattern.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._backend = self._initialize_backend(model_name)
        self._model_router = get_model_router()
        self._last_tool_calls: list[str] = []
        self._current_mode: str = "Agent"

    def _initialize_backend(
        self, model_name: str
    ) -> SupportsStreamingMessages:
        model_lower = model_name.lower()

        # 1. Anthropic (Claude)
        if model_lower.startswith("anthropic/") or "claude" in model_lower:
            api_key = _required_api_key("Anthropic", "ANTHROPIC_API_KEY")
            return TheseusAnthropicClient(api_key=api_key)

        # 2. Google (Gemini)
        elif model_lower.startswith("google/") or "gemini" in model_lower:
            api_key = _required_api_key("Gemini", "GEMINI_API_KEY", "GOOGLE_API_KEY")
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            return TheseusGeminiClient(
                api_key=api_key, base_url=base_url, timeout=120.0,
            )

        # 3. DeepSeek
        elif model_lower.startswith("deepseek/") or "deepseek" in model_lower:
            api_key = _required_api_key("DeepSeek", "DEEPSEEK_API_KEY")
            base_url = "https://api.deepseek.com/v1"
            return TheseusOpenAICompatClient(
                api_key=api_key, base_url=base_url, timeout=120.0,
            )

        # 4. Ollama
        elif model_lower.startswith("ollama/"):
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            return TheseusOpenAICompatClient(
                api_key="ollama", base_url=base_url, timeout=120.0,
            )

        # 5. vLLM / Custom OpenAI Compatible
        elif model_lower.startswith("vllm/"):
            base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1")
            api_key = os.getenv("OPENAI_API_KEY", "vllm")
            return TheseusOpenAICompatClient(
                api_key=api_key, base_url=base_url, timeout=120.0,
            )

        # 6. Default (OpenAI: gpt-4o, o1, etc.)
        else:
            api_key = _required_api_key("OpenAI", "OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", None)
            return TheseusOpenAICompatClient(
                api_key=api_key, base_url=base_url, timeout=120.0,
            )

    async def stream_message(
        self, request: ApiMessageRequest,
    ) -> AsyncIterator[ApiStreamEvent]:
        """Strip provider prefixes and delegate to the backend client."""
        # --- DEBUG: Dump incoming request to Router ---
        _dump_debug_payload("router_incoming_request", {
            "target_model": self.model_name,
            "request": request,
        }, debug_context=request.debug_context)
        # ----------------------------------------------

        # Patch messages to make tool errors extremely explicit for open-source models
        patched_messages = []
        for msg in request.messages:
            if msg.role == "user" and isinstance(msg.content, list):
                for block in msg.content:
                    if getattr(block, "type", None) == "tool_result" and getattr(block, "is_error", False):
                        orig = getattr(block, "content", "")
                        if isinstance(orig, str) and not orig.startswith("[TOOL EXECUTION ERROR]"):
                            prefix = "[TOOL EXECUTION ERROR] The tool failed with the following output:\n"
                            try:
                                setattr(block, "content", f"{prefix}{orig}")
                            except (AttributeError, TypeError):
                                # Frozen Pydantic model — use object.__setattr__
                                try:
                                    object.__setattr__(block, "content", f"{prefix}{orig}")
                                except Exception:
                                    pass
            patched_messages.append(msg)

        # Smart Model Routing: 최근 도구 호출 기반 모델 선택
        routed_model = self._model_router.select_model(
            recent_tool_calls=self._last_tool_calls,
            mode=self._current_mode,
        )
        # 라우팅된 모델이 기본과 다르면 백엔드 재초기화
        if (
            self._model_router.enabled
            and routed_model != self.model_name
        ):
            self._backend = self._initialize_backend(routed_model)
            actual_model = routed_model
            if "/" in actual_model:
                actual_model = actual_model.split("/", 1)[1]
        else:
            actual_model = request.model
            if "/" in actual_model:
                actual_model = actual_model.split("/", 1)[1]

        modified_request = ApiMessageRequest(
            model=actual_model,
            messages=patched_messages,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            tools=request.tools,
            debug_context=request.debug_context,
        )

        # 도구 호출 추적 초기화 (이번 턴)
        turn_tool_calls: list[str] = []

        async for event in self._backend.stream_message(modified_request):
            if isinstance(event, ApiMessageCompleteEvent):
                if event.usage:
                    try:
                        from theseus_engine.engine.cost_tracker import CostTracker
                        CostTracker.get_or_create().record_usage(
                            model=actual_model,
                            input_tokens=event.usage.input_tokens,
                            output_tokens=event.usage.output_tokens,
                        )
                    except Exception:
                        pass
                # 응답 메시지에서 tool_use 블록을 추출하여 도구 호출 추적
                if hasattr(event, "message") and event.message:
                    for block in getattr(event.message, "content", []):
                        if getattr(block, "type", None) == "tool_use":
                            tool_name = getattr(block, "name", "")
                            if tool_name:
                                turn_tool_calls.append(tool_name)
            yield event

        # 이번 턴의 도구 호출 기록 갱신 (다음 턴 라우팅에 사용)
        self._last_tool_calls = turn_tool_calls
        # 라우팅으로 변경된 백엔드 원복
        if self._model_router.enabled:
            self._backend = self._initialize_backend(self.model_name)

    async def generate(
        self,
        messages: list[dict[str, str]] | list[ConversationMessage],
        system_prompt: str = "",
        max_tokens: int = 4096,
        tools: list[Any] | None = None,
        model: str | None = None,
    ) -> ConversationMessage:
        """Single-turn generation wrapper around stream_message.

        Useful for internal audits, classification, or any non-streaming logic.
        """
        # Convert dict messages to ConversationMessage if needed
        converted_messages: list[ConversationMessage] = []
        for m in messages:
            if isinstance(m, dict):
                converted_messages.append(
                    ConversationMessage(role=m["role"], content=[TextBlock(text=m["content"])])
                )
            else:
                converted_messages.append(m)

        request = ApiMessageRequest(
            model=model or self.model_name,
            messages=converted_messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            tools=tools,
        )

        final_message: ConversationMessage | None = None
        async for event in self.stream_message(request):
            if isinstance(event, ApiMessageCompleteEvent):
                final_message = event.message

        if not final_message:
            raise RuntimeError("LLM failed to generate a complete response.")

        return final_message
