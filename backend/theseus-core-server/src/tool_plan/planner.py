from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable

from src.tool_plan.agent_loop import EmptyToolRegistry, ToolPlanAgentLoop
from src.tool_plan.prompts import TOOL_PLAN_SYSTEM_PROMPT, build_generate_prompt, build_regenerate_prompt
from src.tool_plan.schemas import (
    GeneratedPlanBlock,
    GeneratedToolPlan,
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestEvent,
    ToolPlanRequestedEvent,
    ToolPlanResult,
    ToolPlanSkippedResult,
)
from theseus_engine.wrappers.llm_clients.api_types import (
    SupportsStreamingMessages,
)
from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

ProgressCallback = Callable[[str, int], Awaitable[None] | None]
ChunkCallback = Callable[[str], Awaitable[None] | None]


class ToolPlanPlannerError(RuntimeError):
    pass


class ToolPlanPlanner:
    def __init__(
        self,
        *,
        llm_client: SupportsStreamingMessages | None = None,
        model_name: str | None = None,
        tool_registry=None,
    ) -> None:
        self.model_name = model_name or os.getenv("OPENHARNESS_MODEL", "gpt-4o")
        self.llm_client = llm_client or TheseusLLMClient(self.model_name)
        self.tool_registry = tool_registry or EmptyToolRegistry()

    async def plan(
        self,
        event: ToolPlanRequestEvent,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
        checkpoint: dict | None = None,
        checkpoint_callback: Callable[[dict], Awaitable[None] | None] | None = None,
    ) -> ToolPlanResult | ToolPlanSkippedResult:
        await self._emit_progress(progress_callback, "INTENT_CHECKING", 10)
        generated = await self._generate(
            event,
            checkpoint=checkpoint,
            checkpoint_callback=checkpoint_callback,
            chunk_callback=chunk_callback,
        )

        if generated.intent == "SKIP":
            message = generated.skip_message or (
                "Tool 명세로 만들 목표, 입력, 출력, 실행 조건을 더 구체적으로 알려주세요."
            )
            return ToolPlanSkippedResult(message=message)

        await self._emit_progress(progress_callback, "PLAN_STRUCTURING", 75)
        version = self._resolve_plan_version(event)
        snapshot = self._build_snapshot(generated, version=version, event=event)
        structured = {
            "schemaVersion": 1,
            "planVersion": version,
            "title": snapshot["title"],
            "summary": snapshot["summary"],
            "blocks": snapshot["blocks"],
            "inputs": snapshot["inputs"],
            "outputs": snapshot["outputs"],
            "constraints": snapshot["constraints"],
        }
        raw_markdown = self._build_markdown(snapshot)

        await self._emit_progress(progress_callback, "PLAN_VALIDATING", 90)
        self._validate_snapshot(snapshot)
        await self._emit_progress(progress_callback, "PLAN_COMPLETED", 100)

        return ToolPlanResult(
            rawMarkdown=raw_markdown,
            structuredPlanJson=structured,
            planSnapshot=snapshot,
        )

    async def _generate(
        self,
        event: ToolPlanRequestEvent,
        *,
        checkpoint: dict | None,
        checkpoint_callback: Callable[[dict], Awaitable[None] | None] | None,
        chunk_callback: ChunkCallback | None,
    ) -> GeneratedToolPlan:
        prompt = self._build_prompt(event)
        agent_loop = ToolPlanAgentLoop(
            llm_client=self.llm_client,
            model_name=self.model_name,
            tool_registry=self.tool_registry,
        )

        result = await agent_loop.run(
            initial_prompt=prompt,
            system_prompt=TOOL_PLAN_SYSTEM_PROMPT,
            checkpoint=checkpoint,
            checkpoint_callback=checkpoint_callback,
            chunk_callback=chunk_callback,
        )

        try:
            payload = json.loads(self._extract_json_object(result.final_text))
            return GeneratedToolPlan.model_validate(payload)
        except Exception as exc:
            raise ToolPlanPlannerError(f"Invalid ToolPlan LLM output: {exc}") from exc

    def _build_prompt(self, event: ToolPlanRequestEvent) -> str:
        history = [item.model_dump(mode="json", by_alias=True) for item in event.history]
        if isinstance(event, ToolPlanRegenerationRequestedEvent):
            return build_regenerate_prompt(
                base_plan_version=event.base_plan_version,
                base_plan=event.base_plan.model_dump(mode="json", by_alias=True),
                feedback_items=[item.model_dump(mode="json", by_alias=True) for item in event.feedback_items],
                history=history,
            )
        return build_generate_prompt(prompt=event.prompt, history=history)

    def _resolve_plan_version(self, event: ToolPlanRequestEvent) -> int:
        if isinstance(event, ToolPlanRegenerationRequestedEvent):
            return event.base_plan_version + 1
        return 1

    def _build_snapshot(self, generated: GeneratedToolPlan, *, version: int, event: ToolPlanRequestEvent) -> dict:
        base_block_ids_by_title = self._base_block_ids_by_title(event)
        used_ids: set[str] = set()
        blocks = []

        for index, block in enumerate(generated.blocks, start=1):
            block_id = self._stable_block_id(block, base_block_ids_by_title, used_ids)
            used_ids.add(block_id)
            blocks.append(
                {
                    "blockId": block_id,
                    "title": block.title.strip(),
                    "content": block.content.strip(),
                    "order": block.order or index,
                }
            )

        if not blocks:
            blocks = [
                {
                    "blockId": "requirements-summary",
                    "title": "Requirements Summary",
                    "content": generated.summary or "Define the tool goal, inputs, outputs, and execution policy.",
                    "order": 1,
                }
            ]

        return {
            "schemaVersion": 1,
            "planVersion": version,
            "title": (generated.title or "Tool Plan").strip(),
            "summary": (generated.summary or "").strip(),
            "blocks": sorted(blocks, key=lambda item: item["order"]),
            "inputs": generated.inputs,
            "outputs": generated.outputs,
            "constraints": generated.constraints,
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
        block: GeneratedPlanBlock,
        base_block_ids_by_title: dict[str, str],
        used_ids: set[str],
    ) -> str:
        title_key = block.title.strip().lower()
        candidates = [
            base_block_ids_by_title.get(title_key, ""),
            block.block_id or "",
            self._slugify(block.title),
        ]
        for candidate in candidates:
            normalized = self._slugify(candidate)
            if normalized and normalized not in used_ids:
                return normalized
        base = self._slugify(block.title) or "plan-block"
        suffix = 2
        while f"{base}-{suffix}" in used_ids:
            suffix += 1
        return f"{base}-{suffix}"

    def _build_markdown(self, snapshot: dict) -> str:
        lines = [f"## {snapshot['title']}", "", snapshot.get("summary", "")]
        for block in snapshot["blocks"]:
            lines.extend(
                [
                    "",
                    f"### {block['title']}",
                    f"blockId: {block['blockId']}",
                    block["content"],
                ]
            )
        return "\n".join(lines).strip()

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
