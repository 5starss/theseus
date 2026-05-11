import json
import unittest
from unittest.mock import AsyncMock

from src.tool_plan.planner import ToolPlanPlanner
from src.tool_plan.processor import ToolPlanProcessor
from src.tool_plan.schemas import (
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestedEvent,
    ToolPlanResult,
    ToolPlanSkippedResult,
)
from theseus_engine.models.messages import ConversationMessage, TextBlock
from theseus_engine.wrappers.llm_clients.api_types import ApiMessageCompleteEvent, UsageSnapshot


class FakeRepoContext:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self.repo

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class FakeCheckpointRepo:
    def __init__(self):
        self.started = []
        self.completed = []
        self.failed = []
        self.sequence = 0
        self.events = []
        self.sent = []
        self.event_failures = []
        self.pending = []
        self.heartbeats = []

    def begin_run(self, **kwargs):
        self.started.append(kwargs)

    def heartbeat(self, run_id):
        self.heartbeats.append(run_id)

    def next_event_sequence(self, run_id):
        self.sequence += 1
        return self.sequence

    def record_event(self, event, *, publish_channel=None):
        record = type("Record", (), {})()
        record.id = len(self.events) + 1
        record.run_id = event.run_id
        record.publish_channel = publish_channel
        record.payload_json = event.model_dump(mode="json", by_alias=True)
        self.events.append(record)
        return record

    def mark_event_sent(self, event_id):
        self.sent.append(event_id)

    def mark_event_failed(self, event_id, error):
        self.event_failures.append((event_id, error))

    def pending_events(self, limit=50, *, publish_channel=None):
        if publish_channel is None:
            return self.pending[:limit]
        return [record for record in self.pending if getattr(record, "publish_channel", publish_channel) == publish_channel][:limit]

    def mark_completed(self, run_id):
        self.completed.append(run_id)

    def mark_failed(self, run_id, code, message):
        self.failed.append((run_id, code, message))


class FakePlanner:
    def __init__(self, result):
        self.result = result
        self.events = []

    async def plan(self, event, *, progress_callback=None, chunk_callback=None):
        self.events.append(event)
        if progress_callback is not None:
            await progress_callback("PLAN_DRAFTING", 35)
        if chunk_callback is not None:
            await chunk_callback("draft")
        return self.result


class FakeLlmClient:
    def __init__(self, text: str):
        self.text = text
        self.requests = []

    async def stream_message(self, request):
        self.requests.append(request)
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=[TextBlock(text=self.text)]),
            usage=UsageSnapshot(),
        )


class ToolPlanWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_generate_completed_event_has_tool_plan_payload_and_no_tool_id(self):
        publisher = AsyncMock()
        repo = FakeCheckpointRepo()
        planner = FakePlanner(create_plan_result())
        processor = ToolPlanProcessor(
            publisher=publisher,
            planner=planner,
            checkpoint_repo_factory=lambda: FakeRepoContext(repo),
        )

        await processor.process_message(create_generate_payload())

        self.assertEqual(repo.started[0]["request_type"], "GENERATE_PLAN")
        self.assertEqual(repo.started[0]["mode"], "PLAN")
        self.assertEqual(repo.completed, ["plan-run-1"])
        published_event_types = [call.args[1].event_type for call in publisher.publish.await_args_list]
        self.assertEqual(published_event_types[-1], "TOOL_PLAN_COMPLETED")

        completed = publisher.publish.await_args_list[-1].args[1]
        dumped = completed.model_dump(mode="json", by_alias=True)
        self.assertEqual(dumped["assistantMessage"]["messageType"], "TOOL_PLAN_RESPONSE")
        self.assertEqual(dumped["toolPlan"]["planSnapshot"]["blocks"][0]["blockId"], "analysis-summary")
        self.assertNotIn("toolId", dumped)
        self.assertEqual([event.payload_json["eventSequence"] for event in repo.events], [1, 2, 3, 4])

    async def test_plan_generate_skipped_event_does_not_publish_tool_plan(self):
        publisher = AsyncMock()
        planner = FakePlanner(ToolPlanSkippedResult(message="목표와 입력을 더 구체적으로 알려주세요."))
        processor = ToolPlanProcessor(publisher=publisher, planner=planner)

        await processor.process_message(create_generate_payload(prompt="안녕"))

        skipped = publisher.publish.await_args_list[-1].args[1]
        dumped = skipped.model_dump(mode="json", by_alias=True)
        self.assertEqual(dumped["eventType"], "TOOL_PLAN_SKIPPED")
        self.assertEqual(dumped["assistantMessage"]["messageType"], "CHAT")
        self.assertNotIn("toolPlan", dumped)

    async def test_plan_regenerate_request_is_consumed_as_regenerate_run(self):
        publisher = AsyncMock()
        repo = FakeCheckpointRepo()
        processor = ToolPlanProcessor(
            publisher=publisher,
            planner=FakePlanner(create_plan_result(version=2)),
            checkpoint_repo_factory=lambda: FakeRepoContext(repo),
        )

        await processor.process_message(create_regenerate_payload())

        self.assertEqual(repo.started[0]["request_type"], "REGENERATE_PLAN")
        completed = publisher.publish.await_args_list[-1].args[1]
        self.assertEqual(completed.tool_plan.plan_snapshot["planVersion"], 2)

    async def test_planner_preserves_base_block_id_by_title_on_regeneration(self):
        llm = FakeLlmClient(json.dumps({
            "intent": "TOOL_PLAN",
            "title": "Incident Recovery Tool",
            "summary": "Updated summary",
            "blocks": [
                {
                    "title": "Analysis Summary",
                    "content": "More specific incident analysis.",
                    "order": 1,
                },
                {
                    "title": "Validation Policy",
                    "content": "Validate required log fields.",
                    "order": 2,
                },
            ],
            "inputs": [],
            "outputs": [],
            "constraints": [],
        }))
        planner = ToolPlanPlanner(llm_client=llm)

        result = await planner.plan(ToolPlanRegenerationRequestedEvent.model_validate(create_regenerate_payload()))

        self.assertEqual(result.plan_snapshot["planVersion"], 2)
        self.assertEqual(result.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")
        self.assertEqual(result.plan_snapshot["blocks"][1]["blockId"], "validation-policy")
        self.assertIn("blockId: analysis-summary", result.raw_markdown)

    async def test_planner_returns_skipped_result_for_invalid_intent(self):
        llm = FakeLlmClient(json.dumps({
            "intent": "SKIP",
            "skipMessage": "Tool 명세로 만들 목표, 입력, 출력, 실행 조건을 더 구체적으로 알려주세요.",
        }))
        planner = ToolPlanPlanner(llm_client=llm)

        result = await planner.plan(ToolPlanRequestedEvent.model_validate(create_generate_payload(prompt="그냥 잡담")))

        self.assertIsInstance(result, ToolPlanSkippedResult)
        self.assertIn("목표", result.message)


def create_plan_result(version: int = 1) -> ToolPlanResult:
    snapshot = {
        "schemaVersion": 1,
        "planVersion": version,
        "title": "Incident Recovery Tool",
        "summary": "Analyze incident logs.",
        "blocks": [
            {
                "blockId": "analysis-summary",
                "title": "Analysis Summary",
                "content": "Analyze recent incident logs.",
                "order": 1,
            }
        ],
        "inputs": [],
        "outputs": [],
        "constraints": [],
        "generatedAt": "2026-05-11T00:00:00+00:00",
    }
    return ToolPlanResult(
        rawMarkdown="## Incident Recovery Tool\n\n### Analysis Summary\nblockId: analysis-summary\nAnalyze recent incident logs.",
        structuredPlanJson=snapshot,
        planSnapshot=snapshot,
    )


def create_generate_payload(prompt: str = "장애 로그 복구 가이드 Tool 명세를 작성해줘."):
    return {
        "eventType": "TOOL_PLAN_REQUESTED",
        "mode": "PLAN",
        "runId": "plan-run-1",
        "projectId": 1,
        "chatSessionId": 2,
        "requestedByUserId": 3,
        "requestedByProjectMemberId": 4,
        "prompt": prompt,
        "history": [
            {
                "role": "user",
                "messageType": "CHAT",
                "contentType": "TEXT",
                "content": "장애 로그가 자주 발생해.",
            }
        ],
        "requestedAt": "2026-05-11T10:00:00",
    }


def create_regenerate_payload():
    return {
        "eventType": "TOOL_PLAN_REGENERATION_REQUESTED",
        "mode": "PLAN",
        "runId": "plan-run-2",
        "projectId": 1,
        "chatSessionId": 2,
        "baseToolPlanId": 10,
        "planGroupId": 1,
        "basePlanVersion": 1,
        "basePlan": {
            "rawMarkdown": "## Incident Recovery Tool",
            "structuredPlanJson": {"schemaVersion": 1, "planVersion": 1},
            "planSnapshot": {
                "schemaVersion": 1,
                "planVersion": 1,
                "title": "Incident Recovery Tool",
                "summary": "Analyze incident logs.",
                "blocks": [
                    {
                        "blockId": "analysis-summary",
                        "title": "Analysis Summary",
                        "content": "Analyze logs.",
                        "order": 1,
                    }
                ],
                "inputs": [],
                "outputs": [],
                "constraints": [],
            },
        },
        "feedbackItems": [
            {
                "blockId": "analysis-summary",
                "comment": "장애 원인을 더 구체적으로 작성해줘.",
            }
        ],
        "history": [],
        "requestedAt": "2026-05-11T10:05:00",
    }


if __name__ == "__main__":
    unittest.main()
