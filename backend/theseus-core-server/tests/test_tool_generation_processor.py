import unittest
from unittest.mock import AsyncMock

from src.tool_generation.processor import ToolGenerationProcessor
from src.tool_generation.schemas import (
    ToolGenerationRequestEvent,
    ToolRegenerationRequestEvent,
)
from src.tool_plan.schemas import (
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestedEvent,
    ToolPlanResult,
    ToolPlanSkippedResult,
)


class FakePlanner:
    def __init__(self, result):
        self.result = result
        self.events = []

    async def plan(self, event, *, progress_callback=None, chunk_callback=None):
        self.events.append(event)
        if progress_callback is not None:
            await progress_callback("PLAN_DRAFTING", 35)
        if chunk_callback is not None:
            await chunk_callback("raw-json-delta")
        return self.result


class ToolGenerationCompatibilityProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_adapts_legacy_request_to_tool_plan_and_publishes_legacy_events(self):
        publisher = AsyncMock()
        planner = FakePlanner(create_plan_result(version=1))
        processor = ToolGenerationProcessor(publisher=publisher, planner=planner)

        await processor.process_generation(create_generation_event())

        self.assertEqual(len(planner.events), 1)
        self.assertIsInstance(planner.events[0], ToolPlanRequestedEvent)
        self.assertEqual(planner.events[0].prompt, "make a recovery tool")

        published_event_types = [call.args[1].event_type for call in publisher.publish.await_args_list]
        self.assertEqual(published_event_types, ["progress", "chunk", "TOOL_GENERATION_COMPLETED"])

        completed = publisher.publish.await_args_list[-1].args[1]
        self.assertEqual(completed.run_id, "run-1")
        self.assertEqual(completed.tool_id, 7)
        self.assertEqual(completed.assistant_message.message_type, "TOOL_DRAFT_RESPONSE")
        self.assertEqual(completed.tool_draft.structured_plan_json["planVersion"], 1)

    async def test_generation_splits_rendered_markdown_into_legacy_chunks(self):
        raw_markdown = "\n".join(
            [
                "## PLAN v1",
                "line 1",
                "line 2",
                "line 3",
                "line 4",
                "line 5",
                "line 6",
                "line 7",
                "line 8",
            ]
        )
        publisher = AsyncMock()
        planner = FakePlanner(create_plan_result(version=1, raw_markdown=raw_markdown))
        processor = ToolGenerationProcessor(publisher=publisher, planner=planner)

        await processor.process_generation(create_generation_event())

        chunks = [
            call.args[1].content
            for call in publisher.publish.await_args_list
            if call.args[1].event_type == "chunk"
        ]
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), raw_markdown)

    async def test_regeneration_adapts_base_draft_and_publishes_legacy_completed_event(self):
        publisher = AsyncMock()
        planner = FakePlanner(create_plan_result(version=2))
        processor = ToolGenerationProcessor(publisher=publisher, planner=planner)

        await processor.process_regeneration(create_regeneration_event())

        self.assertEqual(len(planner.events), 1)
        self.assertIsInstance(planner.events[0], ToolPlanRegenerationRequestedEvent)
        self.assertEqual(planner.events[0].base_plan_version, 1)
        self.assertEqual(planner.events[0].feedback_items[0].block_id, "analysis-summary")

        completed = publisher.publish.await_args_list[-1].args[1]
        self.assertEqual(completed.event_type, "TOOL_GENERATION_COMPLETED")
        self.assertEqual(completed.assistant_message.message_type, "TOOL_REGENERATE_RESPONSE")
        self.assertEqual(completed.tool_draft.structured_plan_json["planVersion"], 2)

    async def test_regeneration_publishes_failed_event_when_base_version_mismatches(self):
        publisher = AsyncMock()
        planner = FakePlanner(create_plan_result(version=3))
        processor = ToolGenerationProcessor(publisher=publisher, planner=planner)

        await processor.process_regeneration(create_regeneration_event(base_draft_version=2))

        self.assertEqual(planner.events, [])
        publisher.publish.assert_awaited_once()
        failed = publisher.publish.await_args.args[1]
        self.assertEqual(failed.event_type, "TOOL_GENERATION_FAILED")
        self.assertEqual(failed.code, "AI_REGENERATION_FAILED")
        self.assertIn("Base draft version mismatch", failed.message)

    async def test_skipped_tool_plan_is_published_as_legacy_failed_event(self):
        publisher = AsyncMock()
        planner = FakePlanner(ToolPlanSkippedResult(message="Tool 명세 요청이 아닙니다."))
        processor = ToolGenerationProcessor(publisher=publisher, planner=planner)

        await processor.process_generation(create_generation_event(prompt="hello"))

        failed = publisher.publish.await_args_list[-1].args[1]
        self.assertEqual(failed.event_type, "TOOL_GENERATION_FAILED")
        self.assertEqual(failed.code, "TOOL_PLAN_SKIPPED")


def create_generation_event(prompt: str = "make a recovery tool") -> ToolGenerationRequestEvent:
    return ToolGenerationRequestEvent.model_validate(
        {
            "eventType": "TOOL_GENERATION_REQUESTED",
            "runId": "run-1",
            "projectId": 1,
            "chatSessionId": 10,
            "toolId": 7,
            "requestedByUserId": 3,
            "requestedByProjectMemberId": 5,
            "prompt": prompt,
            "fileName": "recovery-tool",
            "projectRole": "ADMIN",
            "toolPermission": {
                "canCreateTool": True,
                "canUseTool": True,
                "canUpdateTool": True,
                "canDeleteTool": False,
            },
        }
    )


def create_regeneration_event(base_draft_version: int = 1) -> ToolRegenerationRequestEvent:
    return ToolRegenerationRequestEvent.model_validate(
        {
            "eventType": "TOOL_REGENERATION_REQUESTED",
            "runId": "run-2",
            "projectId": 1,
            "chatSessionId": 10,
            "toolId": 7,
            "requestedByUserId": 3,
            "requestedByProjectMemberId": 5,
            "baseDraftVersion": 1,
            "feedbackItems": [
                {
                    "blockId": "analysis-summary",
                    "comment": "make 504 cause more specific",
                }
            ],
            "baseDraft": {
                "toolId": 7,
                "projectId": 1,
                "chatSessionId": 10,
                "rawMarkdown": "## PLAN v1",
                "structuredPlanJson": {
                    "schemaVersion": 1,
                    "planVersion": base_draft_version,
                    "blocks": [
                        {
                            "blockId": "analysis-summary",
                            "title": "Analysis",
                            "content": "Old content",
                        }
                    ],
                },
                "draftSnapshot": {"schemaVersion": 1, "planVersion": base_draft_version},
                "draftPhase": "REVIEW",
            },
            "projectRole": "ADMIN",
            "toolPermission": {
                "canCreateTool": True,
                "canUseTool": True,
                "canUpdateTool": True,
                "canDeleteTool": False,
            },
        }
    )


def create_plan_result(version: int, raw_markdown: str | None = None) -> ToolPlanResult:
    return ToolPlanResult.model_validate(
        {
            "rawMarkdown": raw_markdown or f"## PLAN v{version}",
            "structuredPlanJson": {
                "schemaVersion": 1,
                "planVersion": version,
                "blocks": [
                    {
                        "blockId": "analysis-summary",
                        "title": "Analysis",
                        "content": f"Content v{version}",
                    }
                ],
            },
            "planSnapshot": {"schemaVersion": 1, "planVersion": version},
        }
    )


if __name__ == "__main__":
    unittest.main()
