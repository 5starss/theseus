import json
import re
import unittest
from pathlib import Path

from src.tool_build.schemas import (
    ToolArtifactPayload,
    ToolBuildChunkEvent,
    ToolBuildCompletedEvent,
    ToolBuildFailedEvent,
    ToolBuildProgressEvent,
    ToolBuildRequestedEvent,
)
from src.tool_plan.schemas import (
    AssistantMessagePayload,
    ToolPlanChunkEvent,
    ToolPlanCompletedEvent,
    ToolPlanFailedEvent,
    ToolPlanPayload,
    ToolPlanProgressEvent,
    ToolPlanRegenerationRequestedEvent,
    ToolPlanRequestedEvent,
    ToolPlanSkippedEvent,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_DOC = ROOT / "docs/api/tool-generation-kafka-contract.md"
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots/worker_contracts"


class WorkerContractTests(unittest.TestCase):
    def test_tool_plan_request_payload_snapshots(self):
        self.assert_snapshot(
            "tool_plan_requested.json",
            ToolPlanRequestedEvent.model_validate(tool_plan_requested_payload()).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_plan_regeneration_requested.json",
            ToolPlanRegenerationRequestedEvent.model_validate(
                tool_plan_regeneration_requested_payload()
            ).model_dump(mode="json", by_alias=True),
        )

    def test_tool_plan_event_payload_snapshots(self):
        self.assert_snapshot(
            "tool_plan_progress.json",
            ToolPlanProgressEvent(
                runId="plan-run-1",
                eventSequence=1,
                projectId=1,
                chatSessionId=2,
                message="PLAN_DRAFTING",
                progressRate=35,
            ).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_plan_chunk.json",
            ToolPlanChunkEvent(
                runId="plan-run-1",
                eventSequence=2,
                projectId=1,
                chatSessionId=2,
                content="## Incident Recovery Guide Tool",
            ).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_plan_completed.json",
            tool_plan_completed_event().model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_plan_skipped.json",
            ToolPlanSkippedEvent(
                runId="plan-run-1",
                eventSequence=5,
                projectId=1,
                chatSessionId=2,
                assistantMessage=AssistantMessagePayload(
                    messageType="CHAT",
                    contentType="TEXT",
                    content="Tool 명세로 만들 목표, 입력, 출력, 실행 조건을 더 구체적으로 알려주세요.",
                ),
                completedAt="2026-05-11T10:01:00",
            ).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_plan_failed.json",
            ToolPlanFailedEvent(
                runId="plan-run-1",
                eventSequence=6,
                projectId=1,
                chatSessionId=2,
                code="TOOL_PLAN_GENERATION_FAILED",
                message="Invalid ToolPlan LLM output.",
                failedAt="2026-05-11T10:01:00",
            ).model_dump(mode="json", by_alias=True),
        )

    def test_tool_build_payload_snapshots(self):
        self.assert_snapshot(
            "tool_build_requested.json",
            ToolBuildRequestedEvent.model_validate(tool_build_requested_payload()).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_build_progress.json",
            ToolBuildProgressEvent(
                runId="build-run-1",
                eventSequence=1,
                projectId=1,
                chatSessionId=2,
                toolPlanId=10,
                message="TOOL_BUILD_VALIDATING",
                progressRate=55,
            ).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_build_chunk.json",
            ToolBuildChunkEvent(
                runId="build-run-1",
                eventSequence=2,
                projectId=1,
                chatSessionId=2,
                toolPlanId=10,
                content="building",
            ).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_build_completed.json",
            ToolBuildCompletedEvent(
                runId="build-run-1",
                eventSequence=7,
                projectId=1,
                chatSessionId=2,
                toolPlanId=10,
                artifact=ToolArtifactPayload(
                    fileName="incident_recovery_guide.py",
                    moduleName="incident_recovery_guide",
                    artifactPath="projects/1/incident_recovery_guide.py",
                    codeSnapshot="print('ok')",
                    metadataJson={"toolName": "incident_recovery_guide"},
                    displayName="Incident Recovery Guide",
                    displayDescription="Analyzes incident logs and suggests recovery steps.",
                    permissionLevel=1,
                ),
                completedAt="2026-05-11T10:12:00",
            ).model_dump(mode="json", by_alias=True),
        )
        self.assert_snapshot(
            "tool_build_failed.json",
            ToolBuildFailedEvent(
                runId="build-run-1",
                eventSequence=8,
                projectId=1,
                chatSessionId=2,
                toolPlanId=10,
                code="TOOL_BUILD_FAILED",
                message="Tool validation failed.",
                failedAt="2026-05-11T10:12:00",
            ).model_dump(mode="json", by_alias=True),
        )

    def test_api_core_contract_does_not_use_tool_id_before_build_completed(self):
        plan_request = ToolPlanRequestedEvent.model_validate(tool_plan_requested_payload()).model_dump(
            mode="json",
            by_alias=True,
        )
        plan_regenerate = ToolPlanRegenerationRequestedEvent.model_validate(
            tool_plan_regeneration_requested_payload()
        ).model_dump(mode="json", by_alias=True)
        plan_completed = tool_plan_completed_event().model_dump(mode="json", by_alias=True)
        build_request = ToolBuildRequestedEvent.model_validate(tool_build_requested_payload()).model_dump(
            mode="json",
            by_alias=True,
        )

        self.assertNotIn("toolId", plan_request)
        self.assertNotIn("toolId", plan_regenerate)
        self.assertNotIn("toolId", plan_completed)
        self.assertNotIn("toolId", build_request)
        self.assertEqual(build_request["toolPlanId"], 10)
        self.assertEqual(build_request["approvedPlan"]["planSnapshot"]["planVersion"], 1)

    def test_documented_json_examples_parse_against_core_schemas(self):
        examples = examples_by_event_type(CONTRACT_DOC)

        self.assertIn("TOOL_PLAN_REQUESTED", examples)
        self.assertIn("TOOL_PLAN_REGENERATION_REQUESTED", examples)
        self.assertIn("TOOL_PLAN_COMPLETED", examples)

        parsed_request = ToolPlanRequestedEvent.model_validate(examples["TOOL_PLAN_REQUESTED"])
        parsed_regenerate = ToolPlanRegenerationRequestedEvent.model_validate(
            examples["TOOL_PLAN_REGENERATION_REQUESTED"]
        )
        parsed_completed = ToolPlanCompletedEvent.model_validate(examples["TOOL_PLAN_COMPLETED"])

        self.assertEqual(parsed_request.event_type, "TOOL_PLAN_REQUESTED")
        self.assertEqual(parsed_regenerate.base_plan_version, 1)
        self.assertEqual(parsed_completed.tool_plan.plan_snapshot["blocks"][0]["blockId"], "analysis-summary")
        self.assertNotIn("toolId", examples["TOOL_PLAN_REQUESTED"])

    def assert_snapshot(self, file_name: str, payload: dict):
        snapshot_path = SNAPSHOT_DIR / file_name
        actual = canonical_json(payload)
        expected = snapshot_path.read_text(encoding="utf-8")
        self.assertEqual(expected, actual)


def examples_by_event_type(path: Path) -> dict[str, dict]:
    examples: dict[str, dict] = {}
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL):
        payload = json.loads(match.group(1))
        event_type = payload.get("eventType")
        if event_type:
            examples.setdefault(event_type, payload)
    return examples


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def plan_snapshot(version: int = 1) -> dict:
    return {
        "schemaVersion": 1,
        "planVersion": version,
        "title": "Incident Recovery Guide Tool",
        "summary": "Analyzes incident logs and suggests recovery steps.",
        "blocks": [
            {
                "blockId": "analysis-summary",
                "title": "Analysis Summary",
                "content": "Collect and classify recent incident logs.",
                "order": 1,
            }
        ],
        "inputs": [],
        "outputs": [],
        "constraints": [],
        "generatedAt": "2026-05-11T10:01:00+00:00",
    }


def tool_plan_requested_payload() -> dict:
    return {
        "eventType": "TOOL_PLAN_REQUESTED",
        "mode": "PLAN",
        "runId": "plan-run-1",
        "projectId": 1,
        "chatSessionId": 2,
        "requestedByUserId": 3,
        "requestedByProjectMemberId": 4,
        "prompt": "장애 로그 복구 가이드 Tool 명세를 작성해줘.",
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


def tool_plan_regeneration_requested_payload() -> dict:
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
            "rawMarkdown": "## Incident Recovery Guide Tool",
            "structuredPlanJson": plan_snapshot(1),
            "planSnapshot": plan_snapshot(1),
        },
        "feedbackItems": [
            {
                "blockId": "analysis-summary",
                "comment": "장애 원인을 더 구체적으로 나눠줘.",
            }
        ],
        "history": [],
        "requestedAt": "2026-05-11T10:05:00",
    }


def tool_plan_completed_event() -> ToolPlanCompletedEvent:
    return ToolPlanCompletedEvent(
        runId="plan-run-1",
        eventSequence=4,
        projectId=1,
        chatSessionId=2,
        assistantMessage=AssistantMessagePayload(
            messageType="TOOL_PLAN_RESPONSE",
            contentType="MARKDOWN",
            content="## Incident Recovery Guide Tool\n\n### Analysis Summary\nblockId: analysis-summary\nCollect and classify recent incident logs.",
        ),
        toolPlan=ToolPlanPayload(
            rawMarkdown="## Incident Recovery Guide Tool\n\n### Analysis Summary\nblockId: analysis-summary\nCollect and classify recent incident logs.",
            structuredPlanJson=plan_snapshot(1),
            planSnapshot=plan_snapshot(1),
        ),
        completedAt="2026-05-11T10:01:00",
    )


def tool_build_requested_payload() -> dict:
    return {
        "eventType": "TOOL_BUILD_REQUESTED",
        "runId": "build-run-1",
        "projectId": 1,
        "chatSessionId": 2,
        "toolPlanId": 10,
        "planGroupId": 1,
        "approvedByProjectMemberId": 5,
        "approvedPlan": {
            "rawMarkdown": "## Incident Recovery Guide Tool",
            "structuredPlanJson": plan_snapshot(1),
            "planSnapshot": plan_snapshot(1),
        },
        "requestedAt": "2026-05-11T10:10:00",
    }


if __name__ == "__main__":
    unittest.main()
