from __future__ import annotations

import json
import logging
import re
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
from theseus_engine.models.messages import ConversationMessage
from theseus_engine.models.state import AgentMode, PlanPhase
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
        self.max_repair_attempts = max(settings.CORE_TOOL_BUILD_MAX_REPAIR_ATTEMPTS, 0)

    async def build(
        self,
        event: ToolBuildRequestedEvent,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
    ) -> ToolArtifactPayload:
        await self._emit_progress(progress_callback, "TOOL_BUILD_LLM_DRAFTING", 20)
        approved_plan = event.approved_plan.model_dump(mode="json", by_alias=True)
        system_prompt = build_theseus_system_prompt(
            mode=AgentMode.PLAN,
            plan_phase=PlanPhase.EXECUTING,
            plan_content=approved_plan,
            available_tools=[],
            runtime_reminders=[
                "This ToolBuild worker receives an empty tool schema. Do not call create_tool or other tools; return only the task-specific JSON contract from the user message.",
            ],
        )
        spec = await self._generate_tool_spec(
            self._build_tool_message(
                approved_plan=approved_plan,
                project_id=event.project_id,
                chat_session_id=event.chat_session_id,
                tool_plan_id=event.tool_plan_id,
            ),
            system_prompt=system_prompt,
            chunk_callback=chunk_callback,
        )

        last_error: ToolBuildError | None = None
        for attempt in range(0, self.max_repair_attempts + 1):
            try:
                return await self._validate_and_package_spec(event, spec, progress_callback=progress_callback)
            except ToolBuildError as exc:
                last_error = exc
                if attempt >= self.max_repair_attempts:
                    break
                await self._emit_progress(progress_callback, "TOOL_BUILD_REPAIRING", 60 + min(attempt * 5, 10))
                spec = await self._generate_tool_spec(
                    self._build_tool_repair_message(
                        approved_plan=approved_plan,
                        previous_spec=spec.model_dump(mode="json", by_alias=True),
                        error_code=exc.code,
                        error_message=exc.message,
                        attempt=attempt + 1,
                    ),
                    system_prompt=system_prompt,
                    chunk_callback=chunk_callback,
                )

        if last_error is not None:
            raise last_error
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
            raise ToolBuildError(exc.stage.upper(), exc.message) from exc

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
        chunk_callback: ChunkCallback | None = None,
    ) -> GeneratedToolSpec:
        request = ApiMessageRequest(
            model=self.model_name,
            messages=[ConversationMessage.from_user_text(prompt)],
            system_prompt=system_prompt,
            max_tokens=8192,
            tools=[],
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
            raise ToolBuildError("LLM_OUTPUT_INVALID", f"Invalid tool build LLM output: {exc}") from exc

    @staticmethod
    def _build_tool_message(*, approved_plan: dict, project_id: int, chat_session_id: int, tool_plan_id: int) -> str:
        return (
            "Task-specific output contract for this ToolBuild worker request.\n"
            "Follow the approved Theseus plan from the system prompt. For response shape, "
            "use this contract exactly.\n\n"
            "Return exactly one JSON object. Do not include markdown fences or explanatory text.\n\n"
            "The JSON object must have:\n"
            "- toolName: snake_case, lowercase, 3-64 chars\n"
            '- fileName: "<toolName>.py"\n'
            "- moduleName: toolName\n"
            "- displayName: short human-readable name\n"
            "- displayDescription: one sentence\n"
            "- permissionLevel: integer from 1 to 5\n"
            "- pythonCode: complete Python source code\n"
            "- metadataJson: object with inputs, outputs, constraints, and implementationNotes\n\n"
            "Python code requirements:\n"
            "- Import BaseModel from pydantic.\n"
            "- Import BaseTool, ToolExecutionContext, and ToolResult from theseus_engine.tools.core.base_tools.\n"
            "- Define one Pydantic input model class.\n"
            "- Define one BaseTool subclass with name, description, input_model, and permission_level.\n"
            "- Implement async execute(self, arguments: <InputModel>, context: ToolExecutionContext) -> ToolResult.\n"
            "- Return ToolResult(output=<string or JSON-serializable value>) on success.\n"
            "- Return ToolResult(output=<clear error>, is_error=True) on handled failures.\n"
            "- Do not perform network calls unless the approved plan explicitly requires them.\n"
            "- Do not read or write arbitrary local files.\n"
            "- Keep the tool deterministic and safe by default.\n\n"
            "Build an executable Theseus custom tool from this approved ToolPlan.\n"
            f"projectId={project_id}\n"
            f"chatSessionId={chat_session_id}\n"
            f"toolPlanId={tool_plan_id}\n\n"
            "Approved plan payload:\n"
            f"{approved_plan}\n\n"
            "Return only the JSON object described above."
        )

    @staticmethod
    def _build_tool_repair_message(
        *,
        approved_plan: dict,
        previous_spec: dict,
        error_code: str,
        error_message: str,
        attempt: int,
    ) -> str:
        return (
            "Task-specific output contract for this ToolBuild repair request.\n"
            "Follow the approved Theseus plan from the system prompt. Return the same complete JSON schema "
            "used for ToolBuild generation.\n\n"
            "The previous generated tool failed Core validation or sandbox execution.\n"
            f"Repair attempt: {attempt}\n"
            f"Error code: {error_code}\n"
            f"Error message: {error_message}\n\n"
            "Approved plan payload:\n"
            f"{approved_plan}\n\n"
            "Previous generated JSON spec:\n"
            f"{previous_spec}\n\n"
            "Return a corrected complete JSON object using the same schema. "
            "Preserve the approved plan intent. Prefer keeping the same toolName unless "
            "the name itself caused the failure. Return only JSON."
        )

    def _artifact_path(self, module_path: Path) -> str:
        try:
            return str(module_path.relative_to(CUSTOM_TOOLS_DIR))
        except ValueError:
            return str(module_path)

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
