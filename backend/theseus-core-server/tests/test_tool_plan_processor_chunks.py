from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timezone
from typing import Any

from src.tool_plan.schemas import ToolPlanRequestedEvent, ToolPlanResult

_core_runs = types.ModuleType("src.db.repositories.core_runs")
_core_runs.CoreRunAlreadyFinished = type("CoreRunAlreadyFinished", (Exception,), {})
_core_runs.CoreRunLeaseHeld = type("CoreRunLeaseHeld", (Exception,), {})
_core_runs.CoreRunRepository = object
sys.modules.setdefault("src.db.repositories.core_runs", _core_runs)

_planner = types.ModuleType("src.tool_plan.planner")
_planner.ToolPlanPlanner = object
_planner.ToolPlanPlannerError = type("ToolPlanPlannerError", (Exception,), {})
sys.modules.setdefault("src.tool_plan.planner", _planner)

from src.tool_plan.processor import ToolPlanProcessor


class _CollectingPublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(self, key: str, event: Any) -> None:
        del key
        self.events.append(event.model_dump(mode="json", by_alias=True))


class _FakePlanner:
    def __init__(self) -> None:
        self.chunk_callback_seen: Any = "unset"

    async def plan(self, event, **kwargs):
        del event
        self.chunk_callback_seen = kwargs.get("chunk_callback")
        return ToolPlanResult(
            rawMarkdown="### 분석 계획\n\n- 최종 표시용 Markdown입니다.\n",
            structuredPlanJson={
                "goal": "테스트",
                "tasks": [],
            },
            planSnapshot={
                "schemaVersion": "1.0",
                "planVersion": 1,
                "blocks": [
                    {
                        "blockId": "task-1",
                        "title": "테스트",
                        "content": "최종 표시용 Markdown입니다.",
                        "order": 1,
                    }
                ],
            },
        )


class ToolPlanProcessorChunkTest(unittest.IsolatedAsyncioTestCase):
    async def test_processor_does_not_stream_raw_llm_plan_json_chunks(self) -> None:
        publisher = _CollectingPublisher()
        planner = _FakePlanner()
        processor = ToolPlanProcessor(publisher=publisher, planner=planner)
        event = ToolPlanRequestedEvent(
            eventType="TOOL_PLAN_REQUESTED",
            runId="run-1",
            projectId=1,
            chatSessionId=10,
            requestedByUserId=100,
            requestedByProjectMemberId=200,
            prompt="시스템 시간 조회 툴 PLAN 작성",
            requestedAt=datetime.now(timezone.utc),
        )

        await processor.process_plan(event, request_type="GENERATE_PLAN")

        self.assertIsNone(planner.chunk_callback_seen)
        chunks = [
            item["content"]
            for item in publisher.events
            if item.get("eventType") == "chunk"
        ]
        self.assertTrue(chunks)
        self.assertNotIn("```json", "".join(chunks))
        self.assertIn("최종 표시용 Markdown", "".join(chunks))


if __name__ == "__main__":
    unittest.main()
