import unittest
from unittest.mock import AsyncMock

from src.tool_generation.plan_generator import ToolPlanGenerator
from src.tool_generation.processor import ToolGenerationProcessor
from src.tool_generation.schemas import (
    PlanAiRequest,
    ToolGenerationRequestEvent,
    ToolPlanResult,
    ToolRegenerationRequestEvent,
)


class FakeGenerator:
    def __init__(self, result: ToolPlanResult):
        self.result = result
        self.requests: list[PlanAiRequest] = []

    async def generate(self, request: PlanAiRequest) -> ToolPlanResult:
        self.requests.append(request)
        return self.result


class ToolGenerationProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_builds_generate_plan_request_and_publishes_completed_event(self):
        publisher = AsyncMock()
        generator = FakeGenerator(create_plan_result(version=1))
        processor = ToolGenerationProcessor(publisher=publisher, generator=generator)

        await processor.process_generation(create_generation_event())

        self.assertEqual(len(generator.requests), 1)
        ai_request = generator.requests[0]
        self.assertEqual(ai_request.request_type, "GENERATE_PLAN")
        self.assertEqual(ai_request.metadata["toolId"], 7)
        self.assertEqual(ai_request.llm_input["user_message"], "make a recovery tool")
        self.assertIsNone(ai_request.base_draft)

        publisher.publish.assert_awaited_once()
        published = publisher.publish.await_args.args[1]
        self.assertEqual(published.event_type, "TOOL_GENERATION_COMPLETED")
        self.assertEqual(published.assistant_message.message_type, "TOOL_DRAFT_RESPONSE")
        self.assertEqual(published.tool_draft.structured_plan_json["version"], 1)

    async def test_generation_publishes_progress_and_chunk_events_before_completion(self):
        publisher = AsyncMock()
        processor = ToolGenerationProcessor(
            publisher=publisher,
            generator=ToolPlanGenerator(),
        )

        await processor.process_generation(create_generation_event())

        published_event_types = [
            call.args[1].event_type
            for call in publisher.publish.await_args_list
        ]
        self.assertIn("progress", published_event_types)
        self.assertIn("chunk", published_event_types)
        self.assertEqual(published_event_types[-1], "TOOL_GENERATION_COMPLETED")

    async def test_regeneration_fetches_full_base_draft_and_builds_regenerate_plan_request(self):
        publisher = AsyncMock()
        generator = FakeGenerator(create_plan_result(version=2))
        processor = ToolGenerationProcessor(
            publisher=publisher,
            generator=generator,
        )

        await processor.process_regeneration(create_regeneration_event())

        self.assertEqual(len(generator.requests), 1)
        ai_request = generator.requests[0]
        self.assertEqual(ai_request.request_type, "REGENERATE_PLAN")
        self.assertEqual(ai_request.base_draft["version"], 1)
        self.assertEqual(
            ai_request.feedback["feedbackItems"][0],
            {
                "blockId": "analysis-summary",
                "comment": "make 504 cause more specific",
            },
        )

        publisher.publish.assert_awaited_once()
        published = publisher.publish.await_args.args[1]
        self.assertEqual(published.event_type, "TOOL_GENERATION_COMPLETED")
        self.assertEqual(published.assistant_message.message_type, "TOOL_REGENERATE_RESPONSE")
        self.assertEqual(published.tool_draft.structured_plan_json["version"], 2)

    async def test_regeneration_publishes_failed_event_when_base_version_mismatches(self):
        publisher = AsyncMock()
        generator = FakeGenerator(create_plan_result(version=3))
        processor = ToolGenerationProcessor(
            publisher=publisher,
            generator=generator,
        )

        await processor.process_regeneration(create_regeneration_event(base_draft_version=2))

        self.assertEqual(generator.requests, [])
        publisher.publish.assert_awaited_once()
        published = publisher.publish.await_args.args[1]
        self.assertEqual(published.event_type, "TOOL_GENERATION_FAILED")
        self.assertEqual(published.code, "AI_REGENERATION_FAILED")
        self.assertIn("Base draft version mismatch", published.message)


def create_generation_event() -> ToolGenerationRequestEvent:
    return ToolGenerationRequestEvent.model_validate(
        {
            "eventType": "TOOL_GENERATION_REQUESTED",
            "runId": "run-1",
            "projectId": 1,
            "chatSessionId": 10,
            "toolId": 7,
            "requestedByUserId": 3,
            "requestedByProjectMemberId": 5,
            "prompt": "make a recovery tool",
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
                    "version": base_draft_version,
                    "blocks": [
                        {
                            "blockId": "analysis-summary",
                            "title": "Analysis",
                            "content": "Old content",
                        }
                    ],
                },
                "draftSnapshot": {"version": base_draft_version},
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


def create_plan_result(version: int) -> ToolPlanResult:
    return ToolPlanResult.model_validate(
        {
            "rawMarkdown": f"## PLAN v{version}",
            "structuredPlanJson": {
                "version": version,
                "blocks": [
                    {
                        "blockId": "analysis-summary",
                        "title": "Analysis",
                        "content": f"Content v{version}",
                    }
                ],
            },
            "draftSnapshot": {"version": version},
        }
    )


if __name__ == "__main__":
    unittest.main()
