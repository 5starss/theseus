from __future__ import annotations

from typing import Awaitable, Callable

from src.tool_generation.schemas import PlanAiRequest, ToolPlanResult


ProgressCallback = Callable[[str, int], Awaitable[None] | None]
ChunkCallback = Callable[[str], Awaitable[None] | None]

class ToolPlanGenerationNotImplementedError(RuntimeError):
    pass


class ToolPlanGenerator:
    async def generate(
        self,
        request: PlanAiRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
    ) -> ToolPlanResult:
        await self._emit_progress(progress_callback, "Collecting requirements", 10)

        prompt = str(request.llm_input.get("user_message", "")).strip()
        version = self._resolve_version(request)
        summary = self._build_summary(prompt, request)
        blocks = self._build_blocks(prompt, request)

        await self._emit_progress(progress_callback, "Structuring plan blocks", 45)

        raw_markdown = self._build_markdown(version, summary, blocks)
        for chunk in self._split_chunks(raw_markdown):
            await self._emit_chunk(chunk_callback, chunk)

        await self._emit_progress(progress_callback, "Finalizing draft payload", 85)

        structured_plan_json = {
            "version": version,
            "summary": summary,
            "blocks": blocks,
        }
        draft_snapshot = {
            "version": version,
            "requestType": request.request_type,
            "generatedBy": "core-kafka-worker",
            "blockCount": len(blocks),
        }

        await self._emit_progress(progress_callback, "Draft ready", 95)
        return ToolPlanResult(
            raw_markdown=raw_markdown,
            structured_plan_json=structured_plan_json,
            draft_snapshot=draft_snapshot,
        )

    def _resolve_version(self, request: PlanAiRequest) -> int:
        if request.base_draft:
            version = request.base_draft.get("version")
            if isinstance(version, int):
                return version + 1
            if isinstance(version, str) and version.isdigit():
                return int(version) + 1
        return 1

    def _build_summary(self, prompt: str, request: PlanAiRequest) -> str:
        if request.request_type == "REGENERATE_PLAN":
            return f"Regenerated plan for: {prompt or 'existing tool plan'}"
        return f"Initial plan for: {prompt or 'new tool request'}"

    def _build_blocks(self, prompt: str, request: PlanAiRequest) -> list[dict[str, object]]:
        feedback_items = []
        if request.feedback:
            feedback_items = request.feedback.get("feedbackItems", [])

        blocks: list[dict[str, object]] = [
            {
                "blockId": "goal",
                "title": "Goal",
                "content": prompt or "Clarify the user intent and expected outcome.",
            },
            {
                "blockId": "inputs",
                "title": "Inputs",
                "content": "Collect required parameters, source data, and validation rules.",
            },
            {
                "blockId": "execution-flow",
                "title": "Execution Flow",
                "content": (
                    "1. Validate the request.\n"
                    "2. Load required project context.\n"
                    "3. Execute the tool logic.\n"
                    "4. Return a user-facing result with failure handling."
                ),
            },
            {
                "blockId": "safety-and-observability",
                "title": "Safety And Observability",
                "content": (
                    "Enforce permission checks, record audit logs, "
                    "and expose clear failure messages for operators."
                ),
            },
        ]

        if feedback_items:
            feedback_lines = []
            for item in feedback_items:
                block_id = item.get("blockId", "unknown-block")
                comment = item.get("comment", "")
                feedback_lines.append(f"- {block_id}: {comment}")
            blocks.append(
                {
                    "blockId": "feedback-adjustments",
                    "title": "Feedback Adjustments",
                    "content": "\n".join(feedback_lines),
                }
            )

        return blocks

    def _build_markdown(self, version: int, summary: str, blocks: list[dict[str, object]]) -> str:
        sections = [f"## PLAN v{version}", "", summary]
        for block in blocks:
            sections.extend(
                [
                    "",
                    f"### {block['title']}",
                    f"blockId: {block['blockId']}",
                    str(block["content"]),
                ]
            )
        return "\n".join(sections).strip()

    def _split_chunks(self, raw_markdown: str) -> list[str]:
        lines = raw_markdown.splitlines()
        if len(lines) <= 4:
            return [raw_markdown]

        chunks: list[str] = []
        step = max(4, len(lines) // 3)
        for start in range(0, len(lines), step):
            chunks.append("\n".join(lines[start:start + step]))
        return chunks

    async def _emit_progress(self, callback: ProgressCallback | None, message: str, rate: int) -> None:
        if callback is None:
            return
        result = callback(message, rate)
        if result is not None:
            await result

    async def _emit_chunk(self, callback: ChunkCallback | None, chunk: str) -> None:
        if callback is None:
            return
        result = callback(chunk)
        if result is not None:
            await result
