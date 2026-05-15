from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from src.config import resolve_model_name
from src.remote_workspace.read_primitives import build_remote_read_analysis_tools
from src.remote_workspace.resolver import RemoteWorkspaceResolver, resolve_remote_workspace_config
from src.remote_workspace.runtime import (
    REMOTE_WORKSPACE_RUNTIME_KEY,
    register_remote_workspace_config,
)
from src.remote_workspace.schemas import RemoteWorkspaceConnectionConfig
from src.tool_plan.agent_loop import CheckpointCallback, ToolPlanAgentLoop
from src.tool_plan.schemas import (
    ConversationHistoryItem,
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestEvent,
    ToolPlanRequestedEvent,
    ToolPlanResult,
    ToolPlanSkippedResult,
)
from theseus_engine.engine.stream_events import extract_plan_json
from theseus_engine.models.modes import AgentMode, PlanPhase
from theseus_engine.models.messages import ConversationMessage, TextBlock
from theseus_engine.models.state import TheseusStateMachine
from theseus_engine.tools.core.base_tools import ToolRegistry
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

ProgressCallback = Callable[[str, int], Awaitable[None] | None]
ChunkCallback = Callable[[str], Awaitable[None] | None]

logger = logging.getLogger(__name__)

PROJECT_CUSTOM_TOOLS_DIR = (
    Path(__file__).resolve().parents[2] / "theseus_engine" / "custom_tools" / "projects"
)
MAX_EXISTING_CUSTOM_TOOLS_IN_PROMPT = 20
MAX_EXISTING_TOOL_FIELD_LENGTH = 800

_CUSTOM_TOOL_SECURITY_RULES = """\
Generated Theseus custom tool security rules:
- Do not import or call subprocess, os.system, os.popen, shutil, socket, ctypes,
  multiprocessing, signal, pty, resource, tempfile, webbrowser, pickle, or shelve.
- Do not execute shell commands or arbitrary local programs from generated custom tools.
- Do not read or write arbitrary local files unless the approved plan explicitly names
  safe read-only paths.
- For system metrics, prefer psutil and read-only /proc or /sys data. Do not call
  nvidia-smi directly from a generated custom tool.
- If a core requirement depends on a prohibited command or module, expose the limitation
  and propose a safe alternative instead of silently removing that capability.
"""

_CUSTOM_TOOL_SAFETY_CONTEXT = f"""\
Generated custom tool safety context:
- If the request involves creating a Theseus custom tool, the plan must not rely on
  imports, commands, or implementation patterns that generated custom tools are not
  allowed to use.
- If the requested capability appears to require a prohibited import, shell command,
  or local program execution, do not hide that limitation. Keep the main plan safe
  and add a user-visible `alternatives` section with Plan B options such as read-only
  APIs, existing trusted core adapters, Remote Workspace adapters, or explicit
  user/admin approval for a trusted adapter.
- Do not plan subprocess, nvidia-smi, os.system, shell execution, or direct arbitrary
  local program execution inside generated custom tool code.

{_CUSTOM_TOOL_SECURITY_RULES}
"""

_PLAN_VALIDATION_FEEDBACK_SYSTEM_PROMPT = """\
You are Theseus in PLAN mode.

A PLAN draft failed Core validation before it could be saved or shown as an
approved plan candidate. Your job is to turn the raw validation failure into a
helpful Korean assistant response.

Rules:
- Do not output a JSON block.
- Do not use the user-facing term "ToolPlan"; say "PLAN draft", "실행 스펙",
  "승인된 plan", or "생성할 Tool" instead.
- Explain why the draft was rejected in terms the user can act on.
- Identify which requirement conflicts with Core safety rules or execution spec
  validation.
- Propose safe Plan B options, especially existing read-only remote tools or a
  narrower PLAN draft.
- Do not claim that tool execution, file writing, or remote analysis already
  happened.
- If writing a Markdown file is the risky part, separate "produce a Markdown
  report in chat" from "write a file to a path with approval".
- Keep the response concise and practical.
"""

_PLAN_FAILURE_FEEDBACK_SYSTEM_PROMPT = """\
You are Theseus in PLAN mode.

A PLAN generation worker failed before it could produce a valid assistant
response. Your job is to convert the raw worker failure into a helpful Korean
assistant response.

Rules:
- Do not output JSON.
- Do not use the user-facing term "ToolPlan"; say "PLAN draft", "실행 스펙",
  "승인된 plan", or "생성할 Tool" instead.
- Explain the likely stage and root cause in user-actionable terms.
- Give a safe retry instruction and at least one Plan B.
- If the failure is about existing tool artifacts, suggest reuse, extension,
  replacement via approval, or a different toolName/moduleName/fileName.
- Do not claim that remote analysis, tool execution, or file writing succeeded.
- Keep the response concise and practical.
"""

_EXECUTION_SPEC_KEYWORDS = (
    "tool",
    "custom tool",
    "generated tool",
    "remote workspace",
    "deployment",
    "deploy",
    "post-deploy",
    "health check",
    "docker",
    "container",
    "api check",
    "log",
    "resource",
    "monitoring",
    "monitor",
    "툴",
    "도구",
    "생성",
    "만들",
    "원격",
    "리모트",
    "배포",
    "점검",
    "헬스",
    "상태 조회",
    "운영서버",
    "운영 서버",
    "도커",
    "컨테이너",
    "로그",
    "리소스",
    "모니터링",
)
_ALLOWED_EXECUTION_STATUS_VALUES = {"PASS", "WARNING", "FAIL", "SKIPPED", "INFO"}
_READ_ONLY_API_METHODS = {"GET", "HEAD", "OPTIONS"}
_ALLOWED_COMMAND_ROOTS = {
    "docker",
    "df",
    "free",
    "top",
    "uptime",
    "curl",
    "grep",
    "awk",
    "sed",
}
_ALLOWED_DOCKER_SUBCOMMANDS = {"ps", "inspect", "logs"}
_DENIED_COMMAND_PATTERNS = (
    r"\bdocker\s+exec\b",
    r"\bdocker\s+stop\b",
    r"\bdocker\s+restart\b",
    r"\bdocker\s+rm\b",
    r"\bdocker\s+compose\s+up\b",
    r"\bdocker\s+compose\s+down\b",
    r"\bkubectl\b",
    r"\brm\b",
    r"\bmv\b",
    r"\bcp\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bvi\b",
    r"\bnano\b",
    r"\bsystemctl\b",
    r"\bservice\b",
    r"\bkill\b",
    r"\breboot\b",
    r"\bshutdown\b",
)
_DOCKER_INSPECT_REQUIRED_FIELDS = (
    ".State.Status",
    ".RestartCount",
    ".State.ExitCode",
    ".State.OOMKilled",
    ".State.Health",
    ".State.Health.Status",
)


def _slugify_project_id(project_id: int | str | None) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(project_id or "")).strip("_").lower()
    return slug or "default"


def _load_existing_custom_tool_summaries(project_id: int | str | None) -> list[dict[str, Any]]:
    if project_id is None:
        return []

    project_dir = PROJECT_CUSTOM_TOOLS_DIR / _slugify_project_id(project_id)
    if not project_dir.is_dir():
        return []

    summaries: list[dict[str, Any]] = []
    for metadata_path in sorted(project_dir.glob("*.meta.json")):
        if len(summaries) >= MAX_EXISTING_CUSTOM_TOOLS_IN_PROMPT:
            break
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not _is_active_custom_tool_metadata(metadata):
            continue
        summary = _custom_tool_metadata_summary(metadata)
        if summary:
            summaries.append(summary)
    return summaries


def _is_active_custom_tool_metadata(metadata: dict[str, Any]) -> bool:
    if metadata.get("isActive", True) is False:
        return False
    return str(metadata.get("status", "active")).strip().lower() == "active"


def _custom_tool_metadata_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(metadata.get("toolName") or "").strip()
    if not tool_name:
        return {}

    return {
        "toolName": tool_name,
        "displayName": _trim_prompt_value(metadata.get("displayName")),
        "displayDescription": _trim_prompt_value(
            metadata.get("displayDescription") or metadata.get("description")
        ),
        "inputs": _compact_prompt_json(metadata.get("inputs") or metadata.get("inputSchema")),
        "outputs": _compact_prompt_json(metadata.get("outputs") or metadata.get("outputSchema")),
        "constraints": _compact_prompt_json(metadata.get("constraints")),
    }


def _existing_custom_tool_context(project_id: int | str | None) -> str:
    summaries = _load_existing_custom_tool_summaries(project_id)
    if not summaries:
        return ""

    return (
        "Existing active Theseus custom tools for this project:\n"
        f"{json.dumps(summaries, ensure_ascii=False, indent=2)}\n\n"
        "Before planning a new custom tool, compare the user request with the existing "
        "active tool metadata above. If an existing tool already satisfies the request, "
        "do not propose creating a duplicate tool. Instead, propose using the existing "
        "tool. If the existing tool is close but incomplete, propose extending or "
        "renaming it and explain why. Only propose a new tool when no active tool "
        "reasonably covers the requested capability."
    )


def _trim_prompt_value(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) <= MAX_EXISTING_TOOL_FIELD_LENGTH:
        return text
    return f"{text[:MAX_EXISTING_TOOL_FIELD_LENGTH].rstrip()}..."


def _compact_prompt_json(value: Any) -> Any:
    if value in (None, "", [], {}):
        return None
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return _trim_prompt_value(value)
    if len(text) <= MAX_EXISTING_TOOL_FIELD_LENGTH:
        return value
    return f"{text[:MAX_EXISTING_TOOL_FIELD_LENGTH].rstrip()}..."


class ToolPlanPlannerError(RuntimeError):
    pass


class ToolPlanPlanner:
    def __init__(
        self,
        *,
        llm_client: SupportsStreamingMessages | None = None,
        model_name: str | None = None,
        remote_workspace_resolver: RemoteWorkspaceResolver | None = None,
    ) -> None:
        self.model_name = resolve_model_name(model_name)
        self.llm_client = llm_client or TheseusLLMClient(self.model_name)
        self.remote_workspace_resolver = remote_workspace_resolver

    async def plan(
        self,
        event: ToolPlanRequestEvent,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
        checkpoint: dict | None = None,
        checkpoint_callback: CheckpointCallback | None = None,
    ) -> ToolPlanResult | ToolPlanSkippedResult:
        await self._emit_progress(progress_callback, "PLAN_DRAFTING", 10)
        remote_workspace = await resolve_remote_workspace_config(
            project_id=event.project_id,
            remote_workspace_id=event.remote_workspace_id,
            resolver=self.remote_workspace_resolver,
        )
        generated = await self._generate(
            event,
            remote_workspace=remote_workspace,
            chunk_callback=chunk_callback,
            checkpoint=checkpoint,
            checkpoint_callback=checkpoint_callback,
        )
        if isinstance(generated, ToolPlanSkippedResult):
            return generated
        _raw_markdown, structured_plan = generated

        await self._emit_progress(progress_callback, "PLAN_STRUCTURING", 75)
        try:
            self._validate_execution_spec_if_required(structured_plan, event)
        except ToolPlanPlannerError as exc:
            await self._emit_progress(progress_callback, "PLAN_FEEDBACK", 95)
            feedback = await self._generate_validation_failure_feedback(
                event,
                structured_plan=structured_plan,
                failure_message=str(exc),
                remote_workspace=remote_workspace,
            )
            return ToolPlanSkippedResult(message=feedback)
        version = self._resolve_plan_version(event)
        snapshot = self._build_snapshot(structured_plan, version=version, event=event)
        structured = self._build_structured_plan(structured_plan)
        display_markdown = self._build_markdown(snapshot)

        await self._emit_progress(progress_callback, "PLAN_VALIDATING", 90)
        self._validate_snapshot(snapshot)
        await self._emit_progress(progress_callback, "PLAN_COMPLETED", 100)

        return ToolPlanResult(
            rawMarkdown=display_markdown,
            structuredPlanJson=structured,
            planSnapshot=snapshot,
        )

    async def _generate(
        self,
        event: ToolPlanRequestEvent,
        *,
        remote_workspace: RemoteWorkspaceConnectionConfig | None,
        chunk_callback: ChunkCallback | None,
        checkpoint: dict | None = None,
        checkpoint_callback: CheckpointCallback | None = None,
    ) -> tuple[str, dict[str, Any]] | ToolPlanSkippedResult:
        prompt = self._build_prompt(event)
        history_messages = self._history_messages(event)
        tool_registry = self._build_tool_registry(event, remote_workspace=remote_workspace)
        remote_workspace_runtime_key = (
            register_remote_workspace_config(remote_workspace)
            if remote_workspace is not None
            else None
        )
        agent_loop = ToolPlanAgentLoop(
            llm_client=self.llm_client,
            model_name=self.model_name,
            tool_registry=tool_registry,
            tool_metadata={
                "run_id": event.run_id,
                "project_id": event.project_id,
                "chat_session_id": event.chat_session_id,
                "user_id": getattr(event, "requested_by_user_id", None),
                "agent_mode": event.mode,
                "remote_workspace_id": event.remote_workspace_id,
                REMOTE_WORKSPACE_RUNTIME_KEY: remote_workspace_runtime_key,
                "remote_workspace": (
                    remote_workspace.redacted_model_dump(by_alias=True)
                    if remote_workspace is not None
                    else None
                ),
            },
        )
        loop_result = await agent_loop.run(
            initial_prompt=prompt,
            initial_messages=history_messages,
            system_prompt=self._build_system_prompt(
                event,
                available_tools=tuple(tool.name for tool in tool_registry.list_tools()),
            ),
            checkpoint=checkpoint,
            checkpoint_callback=checkpoint_callback,
            # PLAN drafts contain machine-readable JSON. Publish only the
            # parsed display Markdown after validation so users do not see
            # internal IDs or raw JSON while generation is still streaming.
            chunk_callback=None,
        )

        payload = extract_plan_json(loop_result.final_text)
        if payload is None:
            try:
                parsed = json.loads(self._extract_json_object(loop_result.final_text))
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = None
        if payload is None:
            message = self._plain_chat_response(loop_result.final_text)
            if message:
                return ToolPlanSkippedResult(message=message)
            raise ToolPlanPlannerError(
                "Invalid PLAN draft LLM output: no PLAN JSON block was found."
            )
        return loop_result.final_text, payload

    def _build_prompt(self, event: ToolPlanRequestEvent) -> str:
        existing_tool_context = _existing_custom_tool_context(event.project_id)
        existing_tool_section = (
            f"\n\n{existing_tool_context}" if existing_tool_context else ""
        )
        if isinstance(event, ToolPlanRegenerationRequestedEvent):
            feedback = [
                item.model_dump(mode="json", by_alias=True)
                for item in event.feedback_items
            ]
            return (
                "Revise the current plan according to this review feedback.\n\n"
                f"Base plan version: {event.base_plan_version}\n\n"
                "Base plan:\n"
                f"{json.dumps(event.base_plan.model_dump(mode='json', by_alias=True), ensure_ascii=False, indent=2)}\n\n"
                "Feedback:\n"
                f"{json.dumps(feedback, ensure_ascii=False, indent=2)}\n\n"
                f"{_CUSTOM_TOOL_SAFETY_CONTEXT}"
                f"{existing_tool_section}"
            )
        return f"{event.prompt}\n\n{_CUSTOM_TOOL_SAFETY_CONTEXT}{existing_tool_section}"

    def _history_messages(self, event: ToolPlanRequestEvent) -> list[ConversationMessage]:
        messages: list[ConversationMessage] = []
        for item in event.history:
            role = self._normalize_history_role(item.role)
            if role is None:
                continue
            content = self._render_history_content(item)
            if not content.strip():
                continue
            messages.append(
                ConversationMessage(
                    role=role,
                    content=[TextBlock(text=content)],
                )
            )
        return messages

    @staticmethod
    def _normalize_history_role(role: str) -> Literal["user", "assistant"] | None:
        normalized = str(role or "").strip().lower()
        if normalized in {"user", "assistant"}:
            return normalized
        return None

    def _render_history_content(self, item: ConversationHistoryItem) -> str:
        message_type = (item.message_type or "CHAT").upper()
        content_type = (item.content_type or "TEXT").upper()

        if message_type == "TOOL_FEEDBACK" and content_type == "JSON":
            return self._summarize_feedback_content(item.content)
        if message_type == "TOOL_APPROVAL_REQUEST":
            return "Requested tool approval."
        if isinstance(item.content, str):
            return item.content
        if item.content is None:
            return ""
        return json.dumps(item.content, ensure_ascii=False, indent=2)

    @staticmethod
    def _summarize_feedback_content(content: str | dict[str, Any] | list[Any] | None) -> str:
        if isinstance(content, str):
            try:
                payload = json.loads(content)
            except ValueError:
                return content
        else:
            payload = content

        if not isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False, indent=2) if payload is not None else ""

        feedback_items = payload.get("feedbackItems", [])
        if not isinstance(feedback_items, list) or not feedback_items:
            return "Requested PLAN draft feedback changes."

        lines = [f"Requested {len(feedback_items)} PLAN draft revisions:"]
        for item in feedback_items:
            if not isinstance(item, dict):
                continue
            block_id = item.get("blockId", "unknown-block")
            comment = item.get("comment", "")
            lines.append(f"- {block_id}: {comment}")
        return "\n".join(lines)

    def _build_system_prompt(
        self,
        event: ToolPlanRequestEvent,
        *,
        available_tools: tuple[str, ...],
    ) -> str:
        phase = (
            PlanPhase.WAIT_FOR_REVIEW
            if isinstance(event, ToolPlanRegenerationRequestedEvent)
            else PlanPhase.DRAFTING
        )
        state_machine = TheseusStateMachine(initial_mode=AgentMode.PLAN)
        state_machine.plan_phase = phase
        if isinstance(event, ToolPlanRegenerationRequestedEvent):
            state_machine.plan = json.dumps(
                event.base_plan.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                indent=2,
            )
        return state_machine.get_system_prompt(available_tools=available_tools)

    def _build_tool_registry(
        self,
        event: ToolPlanRequestEvent,
        *,
        remote_workspace: RemoteWorkspaceConnectionConfig | None,
    ) -> ToolRegistry:
        del event
        registry = ToolRegistry()
        if remote_workspace is not None:
            for tool in build_remote_read_analysis_tools(remote_workspace):
                registry.register(tool)
        return registry

    async def _generate_validation_failure_feedback(
        self,
        event: ToolPlanRequestEvent,
        *,
        structured_plan: dict[str, Any],
        failure_message: str,
        remote_workspace: RemoteWorkspaceConnectionConfig | None,
    ) -> str:
        """Explain a rejected PLAN draft as an assistant response.

        This keeps invalid plans out of storage while still giving the user a
        useful next step instead of ending with a raw validation error.
        """

        prompt = self._build_validation_failure_feedback_prompt(
            event,
            structured_plan=structured_plan,
            failure_message=failure_message,
            remote_workspace=remote_workspace,
        )
        messages = [ConversationMessage.from_user_text(prompt)]
        try:
            final_text = ""
            collected_text: list[str] = []
            async for llm_event in self.llm_client.stream_message(
                ApiMessageRequest(
                    model=self.model_name,
                    messages=messages,
                    system_prompt=_PLAN_VALIDATION_FEEDBACK_SYSTEM_PROMPT,
                    max_tokens=1400,
                    tools=[],
                    debug_context={
                        "run_id": event.run_id,
                        "project_id": event.project_id,
                        "chat_session_id": event.chat_session_id,
                        "agent_mode": event.mode,
                        "remote_workspace_id": event.remote_workspace_id,
                        "purpose": "plan_validation_feedback",
                    },
                )
            ):
                if isinstance(llm_event, ApiTextDeltaEvent):
                    collected_text.append(llm_event.text)
                elif isinstance(llm_event, ApiMessageCompleteEvent):
                    final_text = llm_event.message.text
            response = self._plain_chat_response(final_text or "".join(collected_text))
            if response:
                return response
        except Exception as exc:
            logger.warning(
                "PLAN validation feedback generation failed. runId=%s error=%s",
                event.run_id,
                exc,
                exc_info=True,
            )
        return self._fallback_validation_failure_feedback(
            event,
            failure_message=failure_message,
            structured_plan=structured_plan,
        )

    def _build_validation_failure_feedback_prompt(
        self,
        event: ToolPlanRequestEvent,
        *,
        structured_plan: dict[str, Any],
        failure_message: str,
        remote_workspace: RemoteWorkspaceConnectionConfig | None,
    ) -> str:
        plan_summary = {
            "goal": structured_plan.get("goal") or structured_plan.get("title"),
            "summary": structured_plan.get("summary"),
            "context": _compact_prompt_json(structured_plan.get("context")),
            "tasks": _compact_prompt_json(structured_plan.get("tasks")),
            "execution_spec": _compact_prompt_json(structured_plan.get("execution_spec")),
            "alternatives": _compact_prompt_json(structured_plan.get("alternatives")),
        }
        if isinstance(event, ToolPlanRegenerationRequestedEvent):
            request_text = self._regeneration_request_summary(event)
        else:
            request_text = event.prompt
        remote_context = (
            {
                "remoteWorkspaceId": event.remote_workspace_id,
                "basePath": remote_workspace.base_path if remote_workspace else None,
                "allowWriteExecution": (
                    remote_workspace.allow_write_execution
                    if remote_workspace
                    else None
                ),
            }
            if event.remote_workspace_id is not None
            else None
        )
        return (
            "The previous PLAN draft was rejected by Core validation before it could be saved.\n"
            "Analyze the failure and give the user a helpful Korean response.\n\n"
            "Original user request:\n"
            f"{request_text}\n\n"
            "Validation failure:\n"
            f"{failure_message}\n\n"
            "Remote Workspace context, redacted:\n"
            f"{json.dumps(remote_context, ensure_ascii=False, indent=2)}\n\n"
            "Rejected PLAN draft summary:\n"
            f"{json.dumps(plan_summary, ensure_ascii=False, indent=2)}\n"
        )

    @staticmethod
    def _regeneration_request_summary(event: ToolPlanRegenerationRequestedEvent) -> str:
        feedback = [
            item.model_dump(mode="json", by_alias=True)
            for item in event.feedback_items
        ]
        return (
            "사용자가 기존 PLAN draft에 대한 수정 요청을 보냈습니다.\n"
            f"Base plan version: {event.base_plan_version}\n"
            f"Feedback: {json.dumps(feedback, ensure_ascii=False)}"
        )

    @staticmethod
    def _fallback_validation_failure_feedback(
        event: ToolPlanRequestEvent,
        *,
        failure_message: str,
        structured_plan: dict[str, Any],
    ) -> str:
        title = str(
            structured_plan.get("goal")
            or structured_plan.get("title")
            or "요청"
        ).strip()
        remote_line = (
            "\n\n선택된 Remote Workspace가 있으므로, 다음 PLAN draft는 원격 환경을 읽기 전용으로 분석하는 범위 안에서 다시 작성해야 합니다."
            if event.remote_workspace_id is not None
            else ""
        )
        return (
            f"생성된 PLAN draft가 Core 검증을 통과하지 못해 저장하지 않았습니다.\n\n"
            f"대상 요청: {title}\n\n"
            "주요 원인:\n"
            f"{failure_message}\n\n"
            "가능한 대안:\n"
            "1. output redirection, shell chaining, 허용 목록 밖 명령을 제거하고 읽기 전용 명령만 사용하는 실행 스펙으로 다시 요청합니다.\n"
            "2. 이미 검증된 remote_* 읽기 도구를 사용하는 AGENT 작업으로 전환해 분석 보고서를 작성합니다.\n"
            "3. md 파일 저장이 꼭 필요하면 저장 위치와 쓰기 승인을 명확히 한 별도 승인 흐름으로 분리합니다.\n\n"
            "다음 요청 예시:\n"
            "`허용된 remote read-only 도구만 사용해서 서비스별 코드 분석 PLAN draft를 다시 작성해줘. md 저장은 제외하고 Markdown 보고서 출력만 포함해줘.`"
            f"{remote_line}"
        )

    async def explain_failure(
        self,
        event: ToolPlanRequestEvent,
        *,
        code: str,
        message: str,
        stage: str | None = None,
    ) -> str:
        """Convert a raw PLAN worker failure into assistant-readable feedback."""

        prompt = self._build_failure_feedback_prompt(
            event,
            code=code,
            message=message,
            stage=stage,
        )
        try:
            final_text = ""
            collected_text: list[str] = []
            async for llm_event in self.llm_client.stream_message(
                ApiMessageRequest(
                    model=self.model_name,
                    messages=[ConversationMessage.from_user_text(prompt)],
                    system_prompt=_PLAN_FAILURE_FEEDBACK_SYSTEM_PROMPT,
                    max_tokens=1200,
                    tools=[],
                    debug_context={
                        "run_id": event.run_id,
                        "project_id": event.project_id,
                        "chat_session_id": event.chat_session_id,
                        "agent_mode": event.mode,
                        "remote_workspace_id": event.remote_workspace_id,
                        "purpose": "plan_failure_feedback",
                        "failure_code": code,
                        "failure_stage": stage,
                    },
                )
            ):
                if isinstance(llm_event, ApiTextDeltaEvent):
                    collected_text.append(llm_event.text)
                elif isinstance(llm_event, ApiMessageCompleteEvent):
                    final_text = llm_event.message.text
            response = self._plain_chat_response(final_text or "".join(collected_text))
            if response:
                return response
        except Exception as exc:
            logger.warning(
                "PLAN failure feedback generation failed. runId=%s code=%s error=%s",
                event.run_id,
                code,
                exc,
                exc_info=True,
            )
        return self._fallback_plan_failure_feedback(code=code, message=message, stage=stage)

    def _build_failure_feedback_prompt(
        self,
        event: ToolPlanRequestEvent,
        *,
        code: str,
        message: str,
        stage: str | None,
    ) -> str:
        request_text = (
            self._regeneration_request_summary(event)
            if isinstance(event, ToolPlanRegenerationRequestedEvent)
            else event.prompt
        )
        return (
            "A PLAN generation worker failed. Explain it to the user in Korean and suggest a safe retry path.\n\n"
            f"runId={event.run_id}\n"
            f"projectId={event.project_id}\n"
            f"chatSessionId={event.chat_session_id}\n"
            f"mode={event.mode}\n"
            f"remoteWorkspaceId={event.remote_workspace_id}\n"
            f"failureCode={code}\n"
            f"failureStage={stage or 'unknown'}\n\n"
            "Original user request or regeneration feedback:\n"
            f"{request_text}\n\n"
            "Raw failure message:\n"
            f"{message}\n"
        )

    @staticmethod
    def _fallback_plan_failure_feedback(*, code: str, message: str, stage: str | None) -> str:
        lowered = message.lower()
        duplicate_hint = any(
            needle in lowered
            for needle in (
                "이미 존재",
                "already exists",
                "duplicate",
                "filename",
                "modulename",
            )
        )
        next_step = (
            "기존 Tool을 재사용/확장할지, 새 toolName/moduleName/fileName으로 다시 생성할지 선택해 다시 요청해야 합니다."
            if duplicate_hint
            else "오류 원인을 반영해 더 좁은 범위의 PLAN draft로 다시 요청하거나, 필요한 승인/환경 조건을 먼저 정리해야 합니다."
        )
        return (
            "PLAN 생성 작업이 실패했습니다.\n\n"
            f"- code: {code}\n"
            f"- stage: {stage or 'unknown'}\n"
            f"- 원인: {message}\n"
            f"- 다음 단계: {next_step}"
        )

    def _resolve_plan_version(self, event: ToolPlanRequestEvent) -> int:
        if isinstance(event, ToolPlanRegenerationRequestedEvent):
            return event.base_plan_version + 1
        return 1

    def _build_structured_plan(self, plan_json: dict[str, Any]) -> dict:
        return dict(plan_json)

    def _build_snapshot(self, plan_json: dict[str, Any], *, version: int, event: ToolPlanRequestEvent) -> dict:
        base_block_ids_by_title = self._base_block_ids_by_title(event)
        used_ids: set[str] = set()
        blocks = []

        tasks = plan_json.get("tasks") if isinstance(plan_json.get("tasks"), list) else []
        for index, task in enumerate(tasks, start=1):
            task_dict = task if isinstance(task, dict) else {"description": str(task)}
            title = str(
                task_dict.get("title")
                or task_dict.get("description")
                or task_dict.get("id")
                or f"Task {index}"
            ).strip()
            explicit_id = str(task_dict.get("id") or "").strip()
            block_id = self._stable_block_id(title, explicit_id, base_block_ids_by_title, used_ids)
            used_ids.add(block_id)
            blocks.append(
                {
                    "blockId": block_id,
                    "title": title,
                    "content": self._task_content(task_dict),
                    "order": self._task_order(task_dict, index),
                }
            )

        if not blocks:
            blocks = [
                {
                    "blockId": "requirements-summary",
                    "title": "Requirements Summary",
                    "content": self._summary_from_plan(plan_json) or event.prompt,
                    "order": 1,
                }
            ]

        return {
            "schemaVersion": 1,
            "planVersion": version,
            "title": self._title_from_plan(plan_json),
            "summary": self._summary_from_plan(plan_json),
            "blocks": sorted(blocks, key=lambda item: item["order"]),
            "inputs": self._list_of_dicts(plan_json.get("inputs")),
            "outputs": self._list_of_dicts(plan_json.get("outputs")),
            "constraints": self._constraints_from_plan(plan_json),
            "alternatives": self._alternatives_from_plan(plan_json),
            "executionSpec": self._execution_spec_from_plan(plan_json),
            "verification": self._verification_from_plan(plan_json),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }

    def _base_block_ids_by_title(self, event: ToolPlanRequestEvent) -> dict[str, str]:
        if not isinstance(event, ToolPlanRegenerationRequestedEvent):
            return {}
        base_blocks = event.base_plan.plan_snapshot.get("blocks") or []
        mapping: dict[str, str] = {}
        for block in base_blocks:
            title = str(block.get("title") or "").strip().lower()
            block_id = str(block.get("blockId") or "").strip()
            if title and block_id:
                mapping[title] = block_id
        return mapping

    def _stable_block_id(
        self,
        title: str,
        explicit_id: str,
        base_block_ids_by_title: dict[str, str],
        used_ids: set[str],
    ) -> str:
        title_key = title.strip().lower()
        candidates = [
            base_block_ids_by_title.get(title_key, ""),
            explicit_id,
            self._slugify(title),
        ]
        for candidate in candidates:
            normalized = self._slugify(candidate)
            if normalized and normalized not in used_ids:
                return normalized
        base = self._slugify(title) or "plan-block"
        suffix = 2
        while f"{base}-{suffix}" in used_ids:
            suffix += 1
        return f"{base}-{suffix}"

    @staticmethod
    def _title_from_plan(plan_json: dict[str, Any]) -> str:
        return str(plan_json.get("goal") or plan_json.get("title") or "PLAN Draft").strip()

    def _summary_from_plan(self, plan_json: dict[str, Any]) -> str:
        context = plan_json.get("context") if isinstance(plan_json.get("context"), dict) else {}
        parts = [
            plan_json.get("summary"),
            plan_json.get("goal"),
            context.get("problem_analysis"),
            context.get("current_state"),
        ]
        return "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())

    @staticmethod
    def _task_content(task: dict[str, Any]) -> str:
        fields = [
            ("Problem", task.get("problem")),
            ("Solution", task.get("solution")),
            ("Description", task.get("description")),
            ("Expected effect", task.get("expected_effect")),
            ("Plan B", task.get("plan_b") or task.get("safe_alternative")),
            ("Target files", task.get("target_files")),
            ("Integration points", task.get("integration_points")),
            ("Dependencies", task.get("sequential_dependencies")),
        ]
        lines = []
        for label, value in fields:
            if value in (None, "", []):
                continue
            if isinstance(value, (list, dict)):
                rendered = json.dumps(value, ensure_ascii=False)
            else:
                rendered = str(value)
            lines.append(f"{label}: {rendered}")
        return "\n".join(lines).strip() or str(task)

    @staticmethod
    def _task_order(task: dict[str, Any], fallback: int) -> int:
        try:
            return int(task.get("order") or fallback)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _constraints_from_plan(plan_json: dict[str, Any]) -> list[str]:
        constraints = plan_json.get("constraints")
        if isinstance(constraints, list):
            return [str(item) for item in constraints if str(item).strip()]
        context = plan_json.get("context") if isinstance(plan_json.get("context"), dict) else {}
        risks = context.get("risks")
        if risks:
            return [str(risks)]
        return []

    @staticmethod
    def _alternatives_from_plan(plan_json: dict[str, Any]) -> list[dict[str, Any]]:
        alternatives = plan_json.get("alternatives")
        if not isinstance(alternatives, list):
            return []
        result: list[dict[str, Any]] = []
        for item in alternatives:
            if isinstance(item, dict):
                result.append(dict(item))
            elif str(item or "").strip():
                result.append({"title": str(item).strip()})
        return result

    @staticmethod
    def _execution_spec_from_plan(plan_json: dict[str, Any]) -> dict[str, Any]:
        execution_spec = plan_json.get("execution_spec")
        if isinstance(execution_spec, dict):
            return dict(execution_spec)
        return {}

    @staticmethod
    def _verification_from_plan(plan_json: dict[str, Any]) -> dict[str, Any]:
        verification = plan_json.get("verification")
        if isinstance(verification, dict):
            return dict(verification)
        return {}

    def _build_markdown(self, snapshot: dict) -> str:
        lines = [f"## {snapshot['title']}"]
        summary = str(snapshot.get("summary") or "").strip()
        if summary:
            lines.extend(["", summary])

        lines.extend(["", "### 주요 작업"])
        for index, block in enumerate(snapshot["blocks"], start=1):
            title = str(block.get("title") or f"작업 {index}").strip()
            lines.append(f"{index}. **{title}**")
            display_content = self._display_block_content(str(block.get("content") or ""))
            if display_content:
                lines.extend(f"   - {line}" for line in display_content)

        constraints = [str(item).strip() for item in snapshot.get("constraints", []) if str(item).strip()]
        if constraints:
            lines.extend(["", "### 주의 사항"])
            lines.extend(f"- {item}" for item in constraints)

        alternative_lines = self._display_alternatives(snapshot.get("alternatives") or [])
        if alternative_lines:
            lines.extend(["", "### 대안 / Plan B"])
            lines.extend(f"- {line}" for line in alternative_lines)

        execution_lines = self._display_execution_spec(snapshot.get("executionSpec") or {})
        if execution_lines:
            lines.extend(["", "### 실행 스펙"])
            lines.extend(f"- {line}" for line in execution_lines)

        verification_lines = self._display_verification(snapshot.get("verification") or {})
        if verification_lines:
            lines.extend(["", "### 검증 기준"])
            lines.extend(f"- {line}" for line in verification_lines)
        return "\n".join(lines).strip()

    @staticmethod
    def _display_block_content(content: str) -> list[str]:
        label_map = {
            "Problem": "문제",
            "Solution": "해결 방향",
            "Description": "구현 내용",
            "Expected effect": "기대 효과",
            "Plan B": "대안",
            "Target files": "영향 파일",
            "Integration points": "연동 지점",
            "Dependencies": "의존 관계",
        }
        lines: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ":" in line:
                label, value = line.split(":", 1)
                display_label = label_map.get(label.strip())
                if display_label:
                    lines.append(f"**{display_label}**: {value.strip()}")
                    continue
            lines.append(line)
        return lines

    @staticmethod
    def _display_alternatives(alternatives: list[dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        for index, alternative in enumerate(alternatives, start=1):
            title = str(
                alternative.get("title")
                or alternative.get("name")
                or f"대안 {index}"
            ).strip()
            reason = str(
                alternative.get("reason")
                or alternative.get("why")
                or alternative.get("description")
                or ""
            ).strip()
            tradeoffs = alternative.get("tradeoffs") or alternative.get("tradeoff")
            when_to_use = alternative.get("when_to_use") or alternative.get("whenToUse")
            parts = [f"**{title}**"]
            if reason:
                parts.append(reason)
            if tradeoffs:
                parts.append(f"트레이드오프: {tradeoffs}")
            if when_to_use:
                parts.append(f"적용 조건: {when_to_use}")
            lines.append(" - ".join(str(part) for part in parts if str(part).strip()))
        return lines

    @staticmethod
    def _display_execution_spec(execution_spec: dict[str, Any]) -> list[str]:
        if not isinstance(execution_spec, dict) or not execution_spec:
            return []

        lines: list[str] = []
        tool_name = str(execution_spec.get("tool_name") or "").strip()
        if tool_name:
            lines.append(f"도구 이름: `{tool_name}`")

        status_values = execution_spec.get("status_values")
        if isinstance(status_values, list) and status_values:
            lines.append(
                "상태값: "
                + ", ".join(f"`{str(item).strip()}`" for item in status_values if str(item).strip())
            )

        inputs = execution_spec.get("inputs")
        if isinstance(inputs, list) and inputs:
            input_names = [
                str(item.get("name") or item.get("key") or "").strip()
                for item in inputs
                if isinstance(item, dict)
            ]
            input_names = [name for name in input_names if name]
            if input_names:
                lines.append("입력값: " + ", ".join(f"`{name}`" for name in input_names[:8]))

        steps = execution_spec.get("steps")
        if isinstance(steps, list) and steps:
            step_titles: list[str] = []
            for step in steps[:8]:
                if not isinstance(step, dict):
                    continue
                step_id = str(step.get("step_id") or step.get("id") or "").strip()
                description = str(step.get("description") or "").strip()
                command_count = len(step.get("commands") or []) if isinstance(step.get("commands"), list) else 0
                label = step_id or description or "step"
                suffix = f" ({command_count} command)" if command_count == 1 else f" ({command_count} commands)"
                step_titles.append(f"`{label}`{suffix}")
            if step_titles:
                lines.append("실행 단계: " + ", ".join(step_titles))

        mvp_exclusions = execution_spec.get("mvp_exclusions")
        if isinstance(mvp_exclusions, list) and mvp_exclusions:
            lines.append(
                "MVP 제외: "
                + ", ".join(str(item).strip() for item in mvp_exclusions[:8] if str(item).strip())
            )

        outputs = execution_spec.get("outputs")
        if isinstance(outputs, dict):
            fields = outputs.get("required_result_fields")
            if isinstance(fields, list) and fields:
                lines.append(
                    "결과 필드: "
                    + ", ".join(f"`{str(item).strip()}`" for item in fields if str(item).strip())
                )

        return lines

    @staticmethod
    def _display_verification(verification: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        success = verification.get("success_criteria")
        if success:
            lines.append(f"성공 기준: {success}")
        manual_checks = verification.get("manual_checks")
        if isinstance(manual_checks, list):
            lines.extend(str(item) for item in manual_checks if str(item).strip())
        elif manual_checks:
            lines.append(str(manual_checks))
        return lines

    def _validate_execution_spec_if_required(
        self,
        plan_json: dict[str, Any],
        event: ToolPlanRequestEvent,
    ) -> None:
        requires_spec = self._requires_execution_spec(plan_json, event)
        execution_spec = plan_json.get("execution_spec")
        if not requires_spec and not isinstance(execution_spec, dict):
            return
        if not isinstance(execution_spec, dict) or not execution_spec:
            raise ToolPlanPlannerError(
                "PLAN draft execution spec invalid: execution_spec is required for "
                "generated tool, remote, deployment, health check, Docker, API, log, "
                "resource, or operating-server diagnostic requests."
            )

        errors: list[str] = []
        self._validate_execution_spec_shape(execution_spec, errors)
        self._validate_execution_spec_command_policy(execution_spec, errors)
        self._validate_execution_spec_api_checks(execution_spec, errors)
        self._validate_execution_spec_steps(execution_spec, errors)
        if errors:
            details = "\n".join(f"- {item}" for item in errors[:20])
            raise ToolPlanPlannerError(
                "PLAN draft execution spec invalid:\n" + details
            )

    @staticmethod
    def _requires_execution_spec(plan_json: dict[str, Any], event: ToolPlanRequestEvent) -> bool:
        if event.remote_workspace_id is not None:
            return True
        searchable = [
            getattr(event, "prompt", ""),
            plan_json.get("goal"),
            plan_json.get("summary"),
            plan_json.get("title"),
            json.dumps(plan_json.get("context") or {}, ensure_ascii=False),
            json.dumps(plan_json.get("tasks") or [], ensure_ascii=False),
        ]
        text = "\n".join(str(item or "") for item in searchable).lower()
        return any(keyword.lower() in text for keyword in _EXECUTION_SPEC_KEYWORDS)

    @staticmethod
    def _validate_execution_spec_shape(execution_spec: dict[str, Any], errors: list[str]) -> None:
        steps = execution_spec.get("steps")
        if steps is not None and not isinstance(steps, list):
            errors.append("execution_spec.steps must be a list when present.")

        status_values = execution_spec.get("status_values")
        if isinstance(status_values, list) and status_values:
            statuses = {str(item).strip().upper() for item in status_values}
            invalid = sorted(statuses - _ALLOWED_EXECUTION_STATUS_VALUES)
            if invalid:
                errors.append(f"execution_spec.status_values contains unsupported statuses: {invalid}.")

    @staticmethod
    def _validate_execution_spec_command_policy(execution_spec: dict[str, Any], errors: list[str]) -> None:
        policy = execution_spec.get("command_policy")
        if policy is None:
            return
        if not isinstance(policy, dict):
            errors.append("execution_spec.command_policy must be an object when present.")
            return
        allowlist = policy.get("allowlist")
        denylist = policy.get("denylist")
        if allowlist is not None and not isinstance(allowlist, list):
            errors.append("execution_spec.command_policy.allowlist must be a list when present.")
        if denylist is not None and not isinstance(denylist, list):
            errors.append("execution_spec.command_policy.denylist must be a list when present.")

    @staticmethod
    def _validate_execution_spec_api_checks(execution_spec: dict[str, Any], errors: list[str]) -> None:
        api_checks = execution_spec.get("api_checks")
        if api_checks in (None, []):
            return
        if not isinstance(api_checks, list):
            errors.append("execution_spec.api_checks must be a list when present.")
            return
        for index, check in enumerate(api_checks, start=1):
            if not isinstance(check, dict):
                errors.append(f"api_checks[{index}] must be an object.")
                continue
            method = str(check.get("method") or "").strip().upper()
            if method not in _READ_ONLY_API_METHODS:
                errors.append(
                    f"api_checks[{index}] uses non-read-only method {method or '<missing>'}; "
                    "MVP API checks allow only GET, HEAD, or OPTIONS."
                )
            if check.get("read_only") is not True:
                errors.append(f"api_checks[{index}].read_only must be true.")

    def _validate_execution_spec_steps(self, execution_spec: dict[str, Any], errors: list[str]) -> None:
        steps = execution_spec.get("steps")
        if not isinstance(steps, list):
            return
        for step_index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                errors.append(f"steps[{step_index}] must be an object.")
                continue

            decision_rules = step.get("decision_rules")
            if isinstance(decision_rules, list):
                self._validate_decision_rules(decision_rules, step_index, errors)

            commands = step.get("commands")
            if isinstance(commands, list):
                for command_index, command_spec in enumerate(commands, start=1):
                    self._validate_command_spec(command_spec, step_index, command_index, errors)

    @staticmethod
    def _validate_decision_rules(
        decision_rules: list[Any],
        step_index: int,
        errors: list[str],
    ) -> None:
        if not decision_rules:
            return
        for rule_index, rule in enumerate(decision_rules, start=1):
            if not isinstance(rule, dict):
                errors.append(f"steps[{step_index}].decision_rules[{rule_index}] must be an object.")
                continue
            status = str(rule.get("status") or "").strip().upper()
            if status not in _ALLOWED_EXECUTION_STATUS_VALUES:
                errors.append(
                    f"steps[{step_index}].decision_rules[{rule_index}] has unsupported status "
                    f"{status or '<missing>'}."
                )
            condition = str(rule.get("condition") or "").strip().lower()
            if "health" in condition and "none" in condition and status == "FAIL":
                errors.append(
                    f"steps[{step_index}].decision_rules[{rule_index}] treats Docker health none as FAIL; "
                    "use SKIPPED or INFO."
                )
            if "healthcheck" in condition and "not configured" in condition and status == "FAIL":
                errors.append(
                    f"steps[{step_index}].decision_rules[{rule_index}] treats missing healthcheck as FAIL; "
                    "use SKIPPED or INFO."
                )

    def _validate_command_spec(
        self,
        command_spec: Any,
        step_index: int,
        command_index: int,
        errors: list[str],
    ) -> None:
        if not isinstance(command_spec, dict):
            errors.append(f"steps[{step_index}].commands[{command_index}] must be an object.")
            return
        command = str(command_spec.get("command") or "").strip()
        if not command:
            return

        command_type = str(command_spec.get("type") or "").strip().lower()
        if command_type not in {"", "read_only"}:
            errors.append(f"steps[{step_index}].commands[{command_index}].type must be read_only.")

        self._validate_command_text(command, step_index, command_index, command_spec, errors)

    def _validate_command_text(
        self,
        command: str,
        step_index: int,
        command_index: int,
        command_spec: dict[str, Any],
        errors: list[str],
    ) -> None:
        lowered = command.lower()
        for pattern in _DENIED_COMMAND_PATTERNS:
            if re.search(pattern, lowered):
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] uses denied command pattern: {pattern}."
                )

        if "$(" in command or "`" in command:
            errors.append(f"steps[{step_index}].commands[{command_index}] uses command substitution.")
        without_stderr_redirect = lowered.replace("2>&1", "")
        if ">" in without_stderr_redirect:
            errors.append(f"steps[{step_index}].commands[{command_index}] uses output redirection.")
        if "&&" in lowered or ";" in lowered:
            errors.append(f"steps[{step_index}].commands[{command_index}] uses shell chaining.")
        if "||" in lowered and "|| true" not in lowered:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] uses unsupported shell fallback; "
                "only `|| true` is allowed for grep no-match handling."
            )

        for segment in self._command_segments(command):
            root = self._command_root(segment)
            if root not in _ALLOWED_COMMAND_ROOTS:
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] command segment "
                    f"`{segment}` is outside the read-only allowlist."
                )
                continue
            if root == "docker":
                self._validate_docker_command_segment(segment, step_index, command_index, command, errors)
            if root == "sed" and " -n" not in f" {segment.lower()} ":
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] uses sed without -n."
                )
            if root == "curl":
                self._validate_curl_command(segment, step_index, command_index, errors)

        failure_policy = str(command_spec.get("failure_policy") or "").strip().lower()
        if "grep" in lowered and ("docker logs" in lowered or "log" in lowered):
            if failure_policy != "ignore_no_match" and "|| true" not in lowered:
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] log grep must use "
                    "failure_policy=ignore_no_match or `|| true` so no matches are not treated as failure."
                )

    @staticmethod
    def _command_segments(command: str) -> list[str]:
        normalized = re.sub(r"\|\|\s*true\s*$", "", command.strip(), flags=re.IGNORECASE)
        return [
            segment.strip()
            for segment in re.split(r"(?<!\|)\|(?!\|)", normalized)
            if segment.strip()
        ]

    @staticmethod
    def _command_root(segment: str) -> str:
        match = re.match(r"\s*([A-Za-z0-9_.-]+)", segment)
        return match.group(1).lower() if match else ""

    @staticmethod
    def _validate_docker_command_segment(
        segment: str,
        step_index: int,
        command_index: int,
        full_command: str,
        errors: list[str],
    ) -> None:
        parts = re.split(r"\s+", segment.strip())
        subcommand = parts[1].lower() if len(parts) > 1 else ""
        if subcommand not in _ALLOWED_DOCKER_SUBCOMMANDS:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] uses unsupported docker subcommand "
                f"{subcommand or '<missing>'}."
            )
        if subcommand == "inspect":
            if "grep" in full_command.lower():
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] must not infer Docker health "
                    "by grepping raw inspect output."
                )
            missing = [
                field for field in _DOCKER_INSPECT_REQUIRED_FIELDS if field not in full_command
            ]
            if missing:
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] docker inspect command "
                    f"missing fields: {missing}."
                )

    @staticmethod
    def _validate_curl_command(
        segment: str,
        step_index: int,
        command_index: int,
        errors: list[str],
    ) -> None:
        lowered = segment.lower()
        if re.search(r"(^|\s)-x\s*(post|put|patch|delete)\b", lowered) or re.search(
            r"--request\s+(post|put|patch|delete)\b",
            lowered,
        ):
            errors.append(
                f"steps[{step_index}].commands[{command_index}] uses a data-changing curl method."
            )

    def _validate_snapshot(self, snapshot: dict) -> None:
        required = ["schemaVersion", "planVersion", "blocks"]
        for key in required:
            if key not in snapshot:
                raise ToolPlanPlannerError(f"planSnapshot missing required field: {key}")
        if not isinstance(snapshot["blocks"], list) or not snapshot["blocks"]:
            raise ToolPlanPlannerError("planSnapshot.blocks must be a non-empty list")
        for block in snapshot["blocks"]:
            for key in ["blockId", "title", "content", "order"]:
                if key not in block or block[key] in (None, ""):
                    raise ToolPlanPlannerError(f"planSnapshot block missing required field: {key}")

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return re.sub(r"-+", "-", slug)

    @staticmethod
    def _extract_json_object(text: str) -> str:
        stripped = text.strip()
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
        if fence_match:
            stripped = fence_match.group(1).strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return stripped[start:end + 1]
        raise ValueError("No JSON object found")

    @staticmethod
    def _plain_chat_response(text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        fence_match = re.fullmatch(r"```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```", stripped, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()
        return stripped

    async def _emit_progress(self, callback: ProgressCallback | None, message: str, rate: int) -> None:
        if callback is None:
            return
        result = callback(message, rate)
        if result is not None:
            await result

    async def _emit_chunk(self, callback: ChunkCallback | None, content: str) -> None:
        if callback is None or not content:
            return
        result = callback(content)
        if result is not None:
            await result
