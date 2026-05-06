import unittest
from unittest.mock import AsyncMock

from src.tool_generation.processor import ToolGenerationProcessor
from src.tool_generation.schemas import (
    PlanAiRequest,
    ToolDraftPayload,
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


class FakeDraftClient:
    def __init__(self, draft: ToolDraftPayload):
        self.draft = draft
        self.requested_tool_ids: list[int] = []

    async def fetch_tool_draft(self, tool_id: int) -> ToolDraftPayload:
        self.requested_tool_ids.append(tool_id)
        return self.draft


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

    async def test_regeneration_fetches_full_base_draft_and_builds_regenerate_plan_request(self):
        base_draft = ToolDraftPayload.model_validate(
            {
                "toolId": 7,
                "projectId": 1,
                "chatSessionId": 10,
                "rawMarkdown": "## PLAN v1",
                "structuredPlanJson": {
                    "version": 1,
                    "blocks": [
                        {
                            "blockId": "analysis-summary",
                            "title": "Analysis",
                            "content": "Old content",
                        }
                    ],
                },
                "draftSnapshot": {"version": 1},
                "draftPhase": "REVIEW",
            }
        )
        publisher = AsyncMock()
        generator = FakeGenerator(create_plan_result(version=2))
        draft_client = FakeDraftClient(base_draft)
        processor = ToolGenerationProcessor(
            publisher=publisher,
            generator=generator,
            draft_client=draft_client,
        )

        await processor.process_regeneration(create_regeneration_event())

        self.assertEqual(draft_client.requested_tool_ids, [7])
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
        base_draft = ToolDraftPayload.model_validate(
            {
                "toolId": 7,
                "projectId": 1,
                "chatSessionId": 10,
                "structuredPlanJson": {"version": 2, "blocks": []},
                "draftSnapshot": {"version": 2},
                "draftPhase": "REVIEW",
            }
        )
        publisher = AsyncMock()
        generator = FakeGenerator(create_plan_result(version=3))
        processor = ToolGenerationProcessor(
            publisher=publisher,
            generator=generator,
            draft_client=FakeDraftClient(base_draft),
        )

        await processor.process_regeneration(create_regeneration_event())

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


def create_regeneration_event() -> ToolRegenerationRequestEvent:
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
