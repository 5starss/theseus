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
from theseus_engine.models.messages import ConversationMessage, TextBlock, ToolUseBlock
from theseus_engine.wrappers.llm_clients.api_types import ApiMessageCompleteEvent, UsageSnapshot
from pydantic import BaseModel


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
        self.skipped = []
        self.failed = []
        self.sequence = 0
        self.events = []
        self.sent = []
        self.event_failures = []
        self.pending = []
        self.heartbeats = []
        self.agent_checkpoints = []

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

    def mark_skipped(self, run_id):
        self.skipped.append(run_id)

    def mark_failed(self, run_id, code, message):
        self.failed.append((run_id, code, message))

    def get_checkpoint(self, run_id):
        if not self.agent_checkpoints:
            checkpoint = type("Checkpoint", (), {})()
            checkpoint.state_machine_json = None
            checkpoint.conversation_json = None
            checkpoint.tool_trace_json = None
            checkpoint.progress_json = None
            return checkpoint
        return self.agent_checkpoints[-1]

    def update_checkpoint(
        self,
        run_id,
        *,
        state_machine_json=None,
        conversation_json=None,
        tool_trace_json=None,
        progress_json=None,
    ):
        checkpoint = type("Checkpoint", (), {})()
        checkpoint.state_machine_json = state_machine_json
        checkpoint.conversation_json = conversation_json
        checkpoint.tool_trace_json = tool_trace_json
        checkpoint.progress_json = progress_json
        self.agent_checkpoints.append(checkpoint)


class FakePlanner:
    def __init__(self, result):
        self.result = result
        self.events = []

    async def plan(self, event, *, progress_callback=None, chunk_callback=None, **kwargs):
        self.events.append(event)
        if progress_callback is not None:
            await progress_callback("PLAN_DRAFTING", 35)
        if chunk_callback is not None:
            await chunk_callback("draft")
        if kwargs.get("checkpoint_callback") is not None:
            checkpoint = kwargs.get("checkpoint") or {}
            kwargs["checkpoint_callback"]({
                "stateMachine": {"schemaVersion": 1, "mode": "Plan", "planPhase": "Drafting"},
                "conversation": [],
                "toolTrace": checkpoint.get("toolTrace") or [],
                "progress": {"completedTurns": 1},
            })
        return self.result


class FakeLlmClient:
    def __init__(self, text: str | list[ConversationMessage]):
        self.text = text
        self.requests = []

    async def stream_message(self, request):
        self.requests.append(request)
        if isinstance(self.text, list):
            message = self.text.pop(0)
            yield ApiMessageCompleteEvent(message=message, usage=UsageSnapshot())
            return
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=[TextBlock(text=self.text)]),
            usage=UsageSnapshot(),
        )


class LookupInput(BaseModel):
    query: str


class FakeToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def get(self, name):
        return self.tools.get(name)

    def to_api_schema(self):
        return [tool.to_api_schema() for tool in self.tools.values()]


class LookupTool:
    name = "lookup_context"
    description = "Looks up context for a ToolPlan."
    input_model = LookupInput

    def to_api_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }

    async def execute(self, arguments: LookupInput, context):
        return type("ToolResult", (), {"output": f"context:{arguments.query}", "is_error": False})()


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
        repo = FakeCheckpointRepo()
        planner = FakePlanner(ToolPlanSkippedResult(message="목표와 입력을 더 구체적으로 알려주세요."))
        processor = ToolPlanProcessor(
            publisher=publisher,
            planner=planner,
            checkpoint_repo_factory=lambda: FakeRepoContext(repo),
        )

        await processor.process_message(create_generate_payload(prompt="안녕"))

        skipped = publisher.publish.await_args_list[-1].args[1]
        dumped = skipped.model_dump(mode="json", by_alias=True)
        self.assertEqual(dumped["eventType"], "TOOL_PLAN_SKIPPED")
        self.assertEqual(dumped["assistantMessage"]["messageType"], "CHAT")
        self.assertNotIn("toolPlan", dumped)
        self.assertEqual(repo.skipped, ["plan-run-1"])
        self.assertEqual(repo.completed, [])

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

    async def test_planner_treats_null_checkpoint_sections_as_empty(self):
        llm = FakeLlmClient(json.dumps({
            "intent": "TOOL_PLAN",
            "title": "Incident Recovery Tool",
            "summary": "Starts from an empty checkpoint.",
            "blocks": [
                {
                    "blockId": "analysis-summary",
                    "title": "Analysis Summary",
                    "content": "Analyze incident logs.",
                    "order": 1,
                }
            ],
            "inputs": [],
            "outputs": [],
            "constraints": [],
        }))
        planner = ToolPlanPlanner(llm_client=llm)

        result = await planner.plan(
            ToolPlanRequestedEvent.model_validate(create_generate_payload()),
            checkpoint={
                "stateMachine": None,
                "conversation": None,
                "toolTrace": None,
                "progress": None,
            },
        )

        self.assertEqual(result.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")

    async def test_planner_ignores_malformed_checkpoint_progress_and_trace(self):
        llm = FakeLlmClient(json.dumps({
            "intent": "TOOL_PLAN",
            "title": "Incident Recovery Tool",
            "summary": "Ignores malformed checkpoint fields.",
            "blocks": [
                {
                    "blockId": "analysis-summary",
                    "title": "Analysis Summary",
                    "content": "Analyze incident logs.",
                    "order": 1,
                }
            ],
            "inputs": [],
            "outputs": [],
            "constraints": [],
        }))
        planner = ToolPlanPlanner(llm_client=llm)

        result = await planner.plan(
            ToolPlanRequestedEvent.model_validate(create_generate_payload()),
            checkpoint={
                "stateMachine": [],
                "conversation": {},
                "toolTrace": {"toolUseId": "bad"},
                "progress": {"completedTurns": "not-a-number"},
            },
        )

        self.assertEqual(result.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")

    async def test_planner_runs_multiturn_tool_loop_and_checkpoints_trace(self):
        first = ConversationMessage(
            role="assistant",
            content=[
                ToolUseBlock(
                    id="toolu_lookup_1",
                    name="lookup_context",
                    input={"query": "incident logs"},
                )
            ],
        )
        second = ConversationMessage(
            role="assistant",
            content=[TextBlock(text=json.dumps({
                "intent": "TOOL_PLAN",
                "title": "Incident Recovery Tool",
                "summary": "Uses looked up context.",
                "blocks": [
                    {
                        "blockId": "analysis-summary",
                        "title": "Analysis Summary",
                        "content": "Analyze incidents with retrieved context.",
                        "order": 1,
                    }
                ],
                "inputs": [],
                "outputs": [],
                "constraints": [],
            }))],
        )
        registry = FakeToolRegistry()
        registry.register(LookupTool())
        checkpoints = []
        planner = ToolPlanPlanner(llm_client=FakeLlmClient([first, second]), tool_registry=registry)

        result = await planner.plan(
            ToolPlanRequestedEvent.model_validate(create_generate_payload()),
            checkpoint_callback=lambda checkpoint: checkpoints.append(checkpoint),
        )

        self.assertEqual(result.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")
        self.assertGreaterEqual(len(checkpoints), 4)
        self.assertEqual(checkpoints[-1]["stateMachine"]["mode"], "Plan")
        self.assertEqual(checkpoints[-1]["stateMachine"]["planPhase"], "Drafting")
        self.assertEqual(checkpoints[-1]["toolTrace"][0]["toolName"], "lookup_context")
        self.assertEqual(checkpoints[-1]["toolTrace"][0]["status"], "completed")
        self.assertIn("context:incident logs", checkpoints[-1]["toolTrace"][0]["toolOutput"])

    async def test_processor_passes_restored_checkpoint_to_planner_and_persists_updates(self):
        publisher = AsyncMock()
        repo = FakeCheckpointRepo()
        repo.update_checkpoint(
            "plan-run-1",
            state_machine_json={"schemaVersion": 1, "mode": "Plan", "planPhase": "Drafting"},
            conversation_json=[],
            tool_trace_json=[{"toolName": "previous"}],
            progress_json={"completedTurns": 0},
        )
        processor = ToolPlanProcessor(
            publisher=publisher,
            planner=FakePlanner(create_plan_result()),
            checkpoint_repo_factory=lambda: FakeRepoContext(repo),
        )

        await processor.process_message(create_generate_payload())

        self.assertGreaterEqual(len(repo.agent_checkpoints), 2)
        self.assertEqual(repo.completed, ["plan-run-1"])

    async def test_planner_restores_legacy_plan_mode_checkpoint_name(self):
        llm = FakeLlmClient(json.dumps({
            "intent": "TOOL_PLAN",
            "title": "Incident Recovery Tool",
            "summary": "Restored from checkpoint.",
            "blocks": [
                {
                    "blockId": "analysis-summary",
                    "title": "Analysis Summary",
                    "content": "Analyze after restore.",
                    "order": 1,
                }
            ],
            "inputs": [],
            "outputs": [],
            "constraints": [],
        }))
        planner = ToolPlanPlanner(llm_client=llm)

        result = await planner.plan(
            ToolPlanRequestedEvent.model_validate(create_generate_payload()),
            checkpoint={
                "stateMachine": {"schemaVersion": 1, "mode": "PLAN", "planPhase": "DRAFTING"},
                "conversation": [],
                "toolTrace": [],
                "progress": {"completedTurns": 0},
            },
        )

        self.assertEqual(result.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")

    async def test_planner_resumes_pending_tool_use_before_next_llm_turn(self):
        final_message = ConversationMessage(
            role="assistant",
            content=[TextBlock(text=json.dumps({
                "intent": "TOOL_PLAN",
                "title": "Incident Recovery Tool",
                "summary": "Resumed after tool use.",
                "blocks": [
                    {
                        "blockId": "analysis-summary",
                        "title": "Analysis Summary",
                        "content": "Use resumed tool result.",
                        "order": 1,
                    }
                ],
                "inputs": [],
                "outputs": [],
                "constraints": [],
            }))],
        )
        registry = FakeToolRegistry()
        registry.register(LookupTool())
        planner = ToolPlanPlanner(llm_client=FakeLlmClient([final_message]), tool_registry=registry)

        result = await planner.plan(
            ToolPlanRequestedEvent.model_validate(create_generate_payload()),
            checkpoint={
                "stateMachine": {"schemaVersion": 1, "mode": "Plan", "planPhase": "Drafting"},
                "conversation": [
                    ConversationMessage.from_user_text("Create a tool plan").model_dump(mode="json"),
                    ConversationMessage(
                        role="assistant",
                        content=[
                            ToolUseBlock(
                                id="toolu_lookup_2",
                                name="lookup_context",
                                input={"query": "resume"},
                            )
                        ],
                    ).model_dump(mode="json"),
                ],
                "toolTrace": [
                    {
                        "toolUseId": "toolu_lookup_2",
                        "toolName": "lookup_context",
                        "toolInput": {"query": "resume"},
                        "status": "started",
                        "turn": 1,
                    }
                ],
                "progress": {"completedTurns": 1},
            },
        )

        request_messages = planner.llm_client.requests[0].messages
        resumed_tool_result_message = request_messages[-2]
        self.assertEqual(resumed_tool_result_message.role, "user")
        self.assertEqual(resumed_tool_result_message.content[0].tool_use_id, "toolu_lookup_2")
        self.assertIn("context:resume", resumed_tool_result_message.content[0].content)
        self.assertEqual(result.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")


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
