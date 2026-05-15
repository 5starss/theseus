from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Awaitable, Callable

from src.builder.system_prompt import build_theseus_system_prompt
from src.config import resolve_model_name, settings
from src.tool_build.schemas import GeneratedToolSpec, ToolArtifactPayload, ToolBuildRequestedEvent
from src.tooling.service import (
    CUSTOM_TOOLS_DIR,
    PROJECT_TOOLS_DIR,
    ServerToolCreationRequest,
    ToolCreationError,
    activate_tool_artifact,
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

    async def _validate_and_package_spec(
        self,
        event: ToolBuildRequestedEvent,
        spec: GeneratedToolSpec,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> ToolArtifactPayload:
        await self._emit_progress(progress_callback, "TOOL_BUILD_VALIDATING", 55)
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
            raise ToolRepairFailure(
                stage=exc.stage,
                code=exc.stage.upper(),
                message=exc.message,
                metadata={"errors": exc.errors},
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
            "- Define one Pydantic input model class.\n"
            "- Define one BaseTool subclass with name, description, input_model, and permission_level.\n"
            "- Implement async execute(self, arguments: <InputModel>, context: ToolExecutionContext) -> ToolResult.\n"
            "- Return ToolResult(output=<string or JSON-serializable value>) on success.\n"
            "- Return ToolResult(output=<clear error>, is_error=True) on handled failures.\n"
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
