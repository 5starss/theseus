from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.builder.system_prompt import build_theseus_system_prompt
from src.config import resolve_model_name, settings
from src.tool_build.schemas import GeneratedToolSpec, ToolArtifactPayload, ToolBuildRequestedEvent
from src.tooling.service import (
    CUSTOM_TOOLS_DIR,
    PROJECT_TOOLS_DIR,
    SANDBOX_ALLOWED_DEPENDENCIES,
    ServerToolCreationRequest,
    ToolCreationError,
    activate_tool_artifact,
    cleanup_failed_tool_artifact,
    cleanup_report_line,
    persist_draft_tool,
    read_tool_metadata,
    run_tool_sandbox_gate_for_artifact,
    validate_draft_tool,
)
from theseus_engine.models.modes import AgentMode, PlanPhase
from theseus_engine.models.messages import ConversationMessage
from theseus_engine.tools.tool_repair import (
    COMMON_CUSTOM_TOOL_SECURITY_RULES,
    ToolRepairFailure,
    ToolRepairLoop,
    ToolRepairPolicy,
    extract_json_object,
)
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int], Awaitable[None] | None]
ChunkCallback = Callable[[str], Awaitable[None] | None]

_TOOL_BUILD_FAILURE_FEEDBACK_SYSTEM_PROMPT = """\
You are Theseus explaining a generated tool build failure to the user.

The build already failed in Core. Your job is not to retry the build directly,
but to convert the raw failure into a concise assistant response in the same
language as the approved plan or original user request. The next PLAN/AGENT turn
can also use this response as context.

Rules:
- Do not output JSON.
- Do not use the user-facing term "ToolPlan"; use language-neutral concepts such
  as "approved plan", "generated tool", "Tool build", or "generation task" instead.
- Explain the likely stage and root cause.
- Give a safe next action and at least one Plan B.
- If the failure is about an existing file/module/tool name, explain that the
  artifact name already exists and suggest reuse, extension, replacement via
  approval, or a new toolName/moduleName/fileName.
- If the failure is from security policy, explain the blocked capability and
  propose a safe alternative instead of relaxing policy.
- Do not claim that any file, remote command, or tool execution succeeded.
- Keep the response practical and under 8 short bullet points or paragraphs.
"""

_DEPENDENCY_KEYS = ("dependencies", "pythonDependencies", "requirements")


def _normalize_dependency_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.split("#", 1)[0].strip()
    text = re.split(r"\s*(?:==|>=|<=|~=|!=|>|<|\[)", text, maxsplit=1)[0].strip()
    return text


def _declared_tool_dependencies(metadata_json: dict[str, Any]) -> list[str]:
    dependencies: list[str] = []
    for key in _DEPENDENCY_KEYS:
        raw_value = metadata_json.get(key)
        if raw_value in (None, "", []):
            continue
        raw_items: list[Any]
        if isinstance(raw_value, str):
            raw_items = [item.strip() for item in re.split(r"[,\n]", raw_value) if item.strip()]
        elif isinstance(raw_value, list):
            raw_items = raw_value
        else:
            continue
        for item in raw_items:
            if isinstance(item, dict):
                item = item.get("name") or item.get("package") or item.get("dependency")
            name = _normalize_dependency_name(item)
            if name and name not in dependencies:
                dependencies.append(name)
    return dependencies


def _validate_declared_sandbox_dependencies(spec: GeneratedToolSpec) -> None:
    dependencies = _declared_tool_dependencies(spec.metadata_json or {})
    if not dependencies:
        return
    allowed_names = {dependency.casefold() for dependency in SANDBOX_ALLOWED_DEPENDENCIES}
    unsupported = [
        dependency
        for dependency in dependencies
        if dependency.casefold() not in allowed_names
    ]
    if not unsupported:
        return
    raise ToolRepairFailure(
        stage="dependency_policy",
        code="DEPENDENCY_POLICY_VIOLATION",
        message=(
            "Generated Tool metadata declares dependencies outside the sandbox allowlist. "
            f"unsupported={unsupported}, allowed={sorted(SANDBOX_ALLOWED_DEPENDENCIES)}. "
            "ToolBuild does not run pip install or Docker build; use an allowed dependency "
            "or update requirements-sandbox.txt and rebuild the sandbox image manually."
        ),
        metadata={
            "declaredDependencies": dependencies,
            "unsupportedDependencies": unsupported,
            "allowedDependencies": sorted(SANDBOX_ALLOWED_DEPENDENCIES),
        },
    )


class ToolBuildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolBuilder:
    def __init__(
        self,
        *,
        llm_client: SupportsStreamingMessages | None = None,
        model_name: str | None = None,
        storage_root: Path = PROJECT_TOOLS_DIR,
    ) -> None:
        self.model_name = resolve_model_name(model_name)
        self.llm_client = llm_client or TheseusLLMClient(self.model_name)
        self.storage_root = storage_root
        self.repair_policy = ToolRepairPolicy.from_env(
            default_attempts=settings.CORE_TOOL_BUILD_MAX_REPAIR_ATTEMPTS,
        )

    async def build(
        self,
        event: ToolBuildRequestedEvent,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
    ) -> ToolArtifactPayload:
        approved_plan = event.approved_plan.model_dump(mode="json", by_alias=True)
        system_prompt = build_theseus_system_prompt(
            mode=AgentMode.PLAN,
            plan_phase=PlanPhase.EXECUTING,
            plan_content=approved_plan,
            available_tools=[],
        )
        debug_context = self._debug_context_for_event(event)
        prompt = self._build_tool_message(
            approved_plan=approved_plan,
            project_id=event.project_id,
            chat_session_id=event.chat_session_id,
            tool_plan_id=event.tool_plan_id,
        )

        repair_loop: ToolRepairLoop[GeneratedToolSpec, ToolArtifactPayload] = ToolRepairLoop(
            llm_client=self.llm_client,
            model_name=self.model_name,
            policy=self.repair_policy,
            debug_context=debug_context,
        )
        result = await repair_loop.run(
            initial_prompt=prompt,
            task_context=(
                "Build an executable Theseus custom tool artifact from this approved plan.\n"
                f"projectId={event.project_id}\n"
                f"chatSessionId={event.chat_session_id}\n"
                f"toolPlanId={event.tool_plan_id}\n\n"
                "Approved plan payload:\n"
                f"{json.dumps(approved_plan, ensure_ascii=False, indent=2)}"
            ),
            candidate_contract=self._tool_spec_contract(),
            generate_candidate=lambda candidate_prompt: self._generate_tool_spec(
                candidate_prompt,
                system_prompt=system_prompt,
                debug_context=debug_context,
                chunk_callback=chunk_callback,
            ),
            validate_candidate=lambda spec: self._validate_and_package_spec(
                event,
                spec,
                progress_callback=progress_callback,
            ),
            parse_candidate_payload=self._parse_tool_spec_payload,
            render_candidate=lambda spec: (
                spec.model_dump(mode="json", by_alias=True) if spec is not None else None
            ),
            on_attempt=lambda attempt, is_repair: self._emit_repair_progress(
                progress_callback,
                attempt,
                is_repair,
            ),
        )

        if result.success and result.value is not None:
            return result.value
        if result.last_failure is not None:
            raise ToolBuildError(
                result.last_failure.code,
                result.final_message(self.repair_policy),
            )
        raise ToolBuildError("TOOL_BUILD_FAILED", "Tool build failed without a captured error.")

    async def explain_failure(
        self,
        event: ToolBuildRequestedEvent,
        *,
        code: str,
        message: str,
        stage: str | None = None,
    ) -> str:
        """Turn a raw Tool build failure into user-actionable feedback.

        The Kafka/API contract remains `code/message`; this method only enriches
        the message so the UI and later agent turns receive useful context.
        """

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
                    system_prompt=_TOOL_BUILD_FAILURE_FEEDBACK_SYSTEM_PROMPT,
                    max_tokens=1200,
                    tools=[],
                    debug_context={
                        **self._debug_context_for_event(event),
                        "purpose": "tool_build_failure_feedback",
                        "failure_code": code,
                        "failure_stage": stage,
                    },
                )
            ):
                if isinstance(llm_event, ApiTextDeltaEvent):
                    collected_text.append(llm_event.text)
                elif isinstance(llm_event, ApiMessageCompleteEvent):
                    final_text = llm_event.message.text or final_text
            response = self._plain_feedback_response(final_text or "".join(collected_text))
            if response:
                return response
        except Exception as exc:
            logger.warning(
                "Tool build failure feedback generation failed. runId=%s code=%s error=%s",
                event.run_id,
                code,
                exc,
                exc_info=True,
            )
        return self._fallback_failure_feedback(code=code, message=message, stage=stage)

    async def _validate_and_package_spec(
        self,
        event: ToolBuildRequestedEvent,
        spec: GeneratedToolSpec,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> ToolArtifactPayload:
        await self._emit_progress(progress_callback, "TOOL_BUILD_VALIDATING", 55)
        _validate_declared_sandbox_dependencies(spec)
        creation_request = ServerToolCreationRequest(
            tool_name=spec.tool_name,
            python_code=spec.python_code,
            permission_level=spec.permission_level,
            project_id=str(event.project_id),
            creator_user_id=str(event.approved_by_project_member_id),
            chat_session_id=event.chat_session_id,
            plan_id=str(event.tool_plan_id),
            run_id=event.run_id,
        )

        paths = None
        try:
            paths, metadata = persist_draft_tool(
                creation_request,
                storage_root=self.storage_root,
            )
            tool_class = validate_draft_tool(paths)

            await self._emit_progress(progress_callback, "TOOL_BUILD_SANDBOXING", 75)
            await run_tool_sandbox_gate_for_artifact(creation_request, paths)

            await self._emit_progress(progress_callback, "TOOL_BUILD_ACTIVATING", 90)
            activate_tool_artifact(
                creation_request,
                paths,
                tool_class=tool_class,
                registry=None,
                tool_permissions=None,
            )
            metadata = read_tool_metadata(paths)
        except ToolCreationError as exc:
            errors = list(exc.errors)
            if paths is not None:
                cleanup_result = cleanup_failed_tool_artifact(
                    paths,
                    request=creation_request,
                    failure_stage=exc.stage,
                    failure_code=exc.stage.upper(),
                    failure_message=exc.message,
                    storage_root=self.storage_root,
                    require_request_match=True,
                )
                errors.append(cleanup_report_line(cleanup_result))
            raise ToolRepairFailure(
                stage=exc.stage,
                code=exc.stage.upper(),
                message=exc.message,
                metadata={"errors": errors},
            ) from exc

        merged_metadata = dict(metadata)
        merged_metadata["generatedSpec"] = {
            "displayName": spec.display_name,
            "displayDescription": spec.display_description,
            "metadataJson": spec.metadata_json,
        }

        return ToolArtifactPayload(
            fileName=paths.module_path.name,
            moduleName=paths.module_name,
            artifactPath=self._artifact_path(paths.module_path),
            codeSnapshot=paths.module_path.read_text(encoding="utf-8"),
            metadataJson=merged_metadata,
            displayName=spec.display_name,
            displayDescription=spec.display_description,
            permissionLevel=spec.permission_level,
        )

    async def _generate_tool_spec(
        self,
        prompt: str,
        *,
        system_prompt: str,
        debug_context: dict[str, object] | None = None,
        chunk_callback: ChunkCallback | None = None,
    ) -> GeneratedToolSpec:
        request = ApiMessageRequest(
            model=self.model_name,
            messages=[ConversationMessage.from_user_text(prompt)],
            system_prompt=system_prompt,
            max_tokens=8192,
            tools=[],
            debug_context=debug_context or {},
        )

        final_text = ""
        async for llm_event in self.llm_client.stream_message(request):
            if isinstance(llm_event, ApiTextDeltaEvent):
                if chunk_callback is not None:
                    result = chunk_callback(llm_event.text)
                    if result is not None:
                        await result
                final_text += llm_event.text
            elif isinstance(llm_event, ApiMessageCompleteEvent):
                final_text = llm_event.message.text or final_text

        try:
            payload = json.loads(self._extract_json_object(final_text))
            return GeneratedToolSpec.model_validate(payload)
        except Exception as exc:
            preview = final_text.strip()
            if len(preview) > 2000:
                preview = preview[:2000] + "..."
            raise ToolRepairFailure(
                stage="llm_output",
                code="LLM_OUTPUT_INVALID",
                message=(
                    f"Invalid tool build LLM output: {exc}\n"
                    f"Raw output preview:\n{preview}"
                ),
                metadata={"rawResponse": preview},
            ) from exc

    @staticmethod
    def _build_tool_message(*, approved_plan: dict, project_id: int, chat_session_id: int, tool_plan_id: int) -> str:
        return (
            "Task-specific output contract for this custom tool artifact build request.\n"
            "Follow the approved Theseus plan from the system prompt. For response shape, "
            "use this contract exactly.\n\n"
            "Return exactly one JSON object. Do not include markdown fences or explanatory text.\n\n"
            "The JSON object must have:\n"
            "- toolName: snake_case, lowercase, 3-64 chars\n"
            '- fileName: "<moduleName>.py"\n'
            "- moduleName: canonical module stem. Use '<toolName>_tool' unless toolName already ends with '_tool'.\n"
            "- displayName: short human-readable name\n"
            "- displayDescription: one sentence\n"
            "- permissionLevel: integer from 1 to 5\n"
            "- pythonCode: complete Python source code\n"
            "- metadataJson: object with inputs, outputs, constraints, and implementationNotes\n\n"
            f"{COMMON_CUSTOM_TOOL_SECURITY_RULES}\n"
            "Python code requirements:\n"
            "- Import BaseModel from pydantic.\n"
            "- Import BaseTool, ToolExecutionContext, and ToolResult from theseus_engine.tools.core.base_tools.\n"
            "- Define one Pydantic input model class named '<ToolClassWithoutTool>Input' "
            "or '<ToolClassName>Input'. Helper/output BaseModel classes are allowed.\n"
            "- Define one BaseTool subclass with name, description, input_model, and permission_level.\n"
            "- Implement async execute(self, arguments: <InputModel>, context: ToolExecutionContext) -> ToolResult.\n"
            "- Return ToolResult(output=<string or JSON-serializable value>) on success.\n"
            "- Return ToolResult(output=<clear error>, is_error=True) on handled failures.\n"
            "- If this tool must invoke another active Theseus tool, use "
            "await context.call_tool(\"tool_name\", {\"arg\": \"value\"}) and handle "
            "ToolResult.is_error. Do not read context.metadata['tool_registry'] directly.\n"
            "- Use nested tool calls only for bounded diagnostic composition; do not "
            "repeat the same tool and arguments, and do not use nested calls for "
            "write/edit/bash/reboot-style actions.\n"
            "- Avoid embedding executable Python source inside another Python source string. "
            "Prefer helper functions, constants, and JSON payloads.\n"
            "- If embedding Python code inside a Python string, use triple single quotes for the outer "
            "string when the inner code contains triple double quote docstrings.\n"
            "- Do not nest unescaped triple double quotes inside another triple double quoted string.\n"
            "- If nested code is unavoidable, do not use docstrings inside the embedded code; use comments instead.\n"
            "- Do not perform network calls unless the approved plan explicitly requires them.\n"
            "- Do not read or write arbitrary local files.\n"
            "- Keep the tool deterministic and safe by default.\n\n"
            "Build an executable Theseus custom tool from this approved plan.\n"
            f"projectId={project_id}\n"
            f"chatSessionId={chat_session_id}\n"
            f"toolPlanId={tool_plan_id}\n\n"
            "Approved plan payload:\n"
            f"{approved_plan}\n\n"
            "Return only the JSON object described above."
        )

    @staticmethod
    def _tool_spec_contract() -> str:
        return (
            "Candidate object schema:\n"
            "{\n"
            '  "toolName": "snake_case logical tool name",\n'
            '  "fileName": "<moduleName>.py",\n'
            '  "moduleName": "canonical module stem, usually <toolName>_tool",\n'
            '  "displayName": "short human-readable name",\n'
            '  "displayDescription": "one sentence",\n'
            '  "permissionLevel": 1,\n'
            '  "pythonCode": "complete Python source code",\n'
            '  "metadataJson": {"inputs": {}, "outputs": {}, "constraints": [], "implementationNotes": "..."}\n'
            "}"
        )

    @staticmethod
    def _parse_tool_spec_payload(payload: dict) -> GeneratedToolSpec:
        return GeneratedToolSpec.model_validate(payload)

    def _artifact_path(self, module_path: Path) -> str:
        try:
            return str(module_path.relative_to(CUSTOM_TOOLS_DIR))
        except ValueError:
            return str(module_path)

    @staticmethod
    def _build_failure_feedback_prompt(
        event: ToolBuildRequestedEvent,
        *,
        code: str,
        message: str,
        stage: str | None,
    ) -> str:
        approved_plan = event.approved_plan.model_dump(mode="json", by_alias=True)
        plan_summary = {
            "goal": approved_plan.get("goal") or approved_plan.get("title"),
            "summary": approved_plan.get("summary"),
            "tasks": approved_plan.get("tasks"),
            "execution_spec": approved_plan.get("execution_spec"),
        }
        return (
            "A generated tool build failed. Explain it to the user in the same language as the approved plan or original request, and suggest a safe next step.\n\n"
            f"runId={event.run_id}\n"
            f"projectId={event.project_id}\n"
            f"chatSessionId={event.chat_session_id}\n"
            f"approvedPlanId={event.tool_plan_id}\n"
            f"failureCode={code}\n"
            f"failureStage={stage or 'unknown'}\n\n"
            "Raw failure message:\n"
            f"{message}\n\n"
            "Approved plan summary:\n"
            f"{json.dumps(plan_summary, ensure_ascii=False, indent=2)}\n"
        )

    @staticmethod
    def _plain_feedback_response(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`").strip()
            if stripped.lower().startswith("markdown"):
                stripped = stripped[len("markdown"):].strip()
        return stripped

    @staticmethod
    def _fallback_failure_feedback(*, code: str, message: str, stage: str | None) -> str:
        lowered = message.lower()
        is_duplicate = any(
            needle in lowered
            for needle in (
                "이미 존재",
                "already exists",
                "duplicate",
                "file name",
                "filename",
                "module name",
                "modulename",
            )
        )
        if is_duplicate:
            return (
                "Tool build가 실패했습니다.\n\n"
                f"- 원인: 같은 Tool 파일명 또는 moduleName의 artifact가 이미 존재합니다. (code={code}, stage={stage or 'unknown'})\n"
                "- recoverable: true\n"
                "- retry_policy: do_not_retry_same_input\n"
                "- 의미: Core가 기존 Tool을 덮어쓰지 않도록 막았기 때문에 새 파일을 저장하지 않았습니다.\n"
                "- 다음 선택지: 기존 Tool을 재사용하거나, 기존 Tool을 개선하는 승인 흐름으로 전환하거나, 새 toolName/moduleName/fileName으로 다시 생성해야 합니다.\n"
                "- 재요청 예시: `기존 Tool과 충돌하지 않도록 새 이름으로 생성해줘. 기존 Tool이 있으면 재사용/확장 여부도 같이 제안해줘.`\n\n"
                f"원본 오류: {message}"
            )
        if "permissionlevel must be an integer" in lowered or "permission_level" in lowered:
            return (
                "Tool build가 실패했습니다.\n\n"
                f"- 원인: permissionLevel은 정수 1~5만 허용됩니다. (code={code}, stage={stage or 'unknown'})\n"
                "- recoverable: true\n"
                "- retry_policy: requires_corrected_permission_level\n"
                "- 다음 선택지: permissionLevel을 1~5 중 하나의 정수로 지정해 다시 생성합니다.\n\n"
                f"원본 오류: {message}"
            )
        return (
            "Tool build가 실패했습니다.\n\n"
            f"- code: {code}\n"
            f"- stage: {stage or 'unknown'}\n"
            f"- 원인: {message}\n"
            "- recoverable: 상황에 따라 다름\n"
            "- retry_policy: 원인을 반영한 수정 없이 같은 입력을 반복하지 않습니다.\n"
            "- 다음 단계: 위 오류를 반영해 PLAN draft를 다시 만들거나, 보안 정책/샌드박스/파일명 충돌 중 어느 조건을 바꿀지 명시해 다시 요청해야 합니다."
        )

    @staticmethod
    def _debug_context_for_event(event: ToolBuildRequestedEvent) -> dict[str, object]:
        return {
            "run_id": event.run_id,
            "project_id": event.project_id,
            "chat_session_id": event.chat_session_id,
            "user_id": event.approved_by_project_member_id,
            "plan_id": event.tool_plan_id,
            "agent_mode": "TOOL_BUILD",
        }

    @staticmethod
    def _extract_json_object(text: str) -> str:
        return extract_json_object(text)

    async def _emit_repair_progress(
        self,
        callback: ProgressCallback | None,
        attempt: int,
        is_repair: bool,
    ) -> None:
        if is_repair:
            await self._emit_progress(
                callback,
                "TOOL_BUILD_REPAIRING",
                60 + min((attempt - 1) * 5, 10),
            )
        else:
            await self._emit_progress(callback, "TOOL_BUILD_LLM_DRAFTING", 20)

    async def _emit_progress(
        self,
        callback: ProgressCallback | None,
        message: str,
        rate: int,
    ) -> None:
        if callback is None:
            return
        result = callback(message, rate)
        if result is not None:
            await result
