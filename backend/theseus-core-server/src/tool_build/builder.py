from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Awaitable, Callable

from src.tool_build.prompts import TOOL_BUILD_SYSTEM_PROMPT, build_tool_prompt
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
        self.model_name = model_name or os.getenv("OPENHARNESS_MODEL", "gpt-4o")
        self.llm_client = llm_client or TheseusLLMClient(self.model_name)
        self.storage_root = storage_root

    async def build(
        self,
        event: ToolBuildRequestedEvent,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
    ) -> ToolArtifactPayload:
        await self._emit_progress(progress_callback, "TOOL_BUILD_LLM_DRAFTING", 20)
        spec = await self._generate_tool_spec(event, chunk_callback=chunk_callback)

        await self._emit_progress(progress_callback, "TOOL_BUILD_VALIDATING", 55)
        creation_request = ServerToolCreationRequest(
            tool_name=spec.tool_name,
            python_code=spec.python_code,
            permission_level=spec.permission_level,
            project_id=str(event.project_id),
            creator_user_id=str(event.approved_by_project_member_id or "unknown"),
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
        )

    async def _generate_tool_spec(
        self,
        event: ToolBuildRequestedEvent,
        *,
        chunk_callback: ChunkCallback | None = None,
    ) -> GeneratedToolSpec:
        approved_plan = event.approved_plan.model_dump(mode="json", by_alias=True)
        prompt = build_tool_prompt(
            approved_plan=approved_plan,
            project_id=event.project_id,
            chat_session_id=event.chat_session_id,
            tool_plan_id=event.tool_plan_id,
        )
        request = ApiMessageRequest(
            model=self.model_name,
            messages=[ConversationMessage.from_user_text(prompt)],
            system_prompt=TOOL_BUILD_SYSTEM_PROMPT,
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
