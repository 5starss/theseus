import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from src.tool_build.builder import ToolBuilder
from src.tool_build.processor import ToolBuildProcessor
from src.tool_build.schemas import (
    ToolArtifactPayload,
    ToolBuildCompletedEvent,
    ToolBuildFailedEvent,
    ToolBuildRequestedEvent,
)
from theseus_engine.models.messages import ConversationMessage, TextBlock
from src.tooling.service import ToolCreationError
from theseus_engine.wrappers.llm_clients.api_types import ApiMessageCompleteEvent, UsageSnapshot


class FakeBuilder:
    def __init__(self, artifact: ToolArtifactPayload):
        self.artifact = artifact
        self.events: list[ToolBuildRequestedEvent] = []

    async def build(self, event, *, progress_callback=None, chunk_callback=None):
        self.events.append(event)
        if progress_callback is not None:
            await progress_callback("TOOL_BUILD_VALIDATING", 55)
        if chunk_callback is not None:
            await chunk_callback("building")
        return self.artifact


class SlowBuilder:
    async def build(self, event, *, progress_callback=None, chunk_callback=None):
        await asyncio.sleep(1)
        return create_artifact()


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


class SequentialFakeLlmClient:
    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.requests = []

    async def stream_message(self, request):
        self.requests.append(request)
        text = self.texts.pop(0)
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=[TextBlock(text=text)]),
            usage=UsageSnapshot(),
        )


class ToolBuildProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_request_publishes_completed_event_with_artifact(self):
        publisher = AsyncMock()
        builder = FakeBuilder(create_artifact())
        processor = ToolBuildProcessor(publisher=publisher, builder=builder)

        await processor.process_message(create_build_payload())

        self.assertEqual(len(builder.events), 1)
        published_event_types = [call.args[1].event_type for call in publisher.publish.await_args_list]
        self.assertIn("progress", published_event_types)
        self.assertIn("chunk", published_event_types)
        self.assertEqual(published_event_types[-1], "TOOL_BUILD_COMPLETED")

        completed = publisher.publish.await_args_list[-1].args[1]
        self.assertEqual(completed.run_id, "build-run-1")
        self.assertEqual(completed.tool_plan_id, 10)
        self.assertEqual(completed.artifact.file_name, "incident_tool.py")

    async def test_duplicate_finished_run_is_skipped(self):
        publisher = AsyncMock()
        builder = FakeBuilder(create_artifact())
        processor = ToolBuildProcessor(publisher=publisher, builder=builder)

        payload = create_build_payload()
        await processor.process_message(payload)
        await processor.process_message(payload)

        self.assertEqual(len(builder.events), 1)
        completed_events = [
            call.args[1]
            for call in publisher.publish.await_args_list
            if call.args[1].event_type == "TOOL_BUILD_COMPLETED"
        ]
        self.assertEqual(len(completed_events), 1)

    async def test_builder_generates_validated_artifact_from_llm_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            llm = FakeLlmClient(create_llm_json())
            builder = ToolBuilder(llm_client=llm, storage_root=Path(tmpdir))

            fake_tool_class = type("IncidentRecoveryTool", (), {"name": "incident_recovery_tool"})
            with patch("src.tool_build.builder.validate_draft_tool", return_value=fake_tool_class), \
                patch("src.tool_build.builder.run_tool_sandbox_gate_for_artifact", new=AsyncMock(return_value={"success": True})), \
                patch("src.tool_build.builder.activate_tool_artifact", return_value=False):
                artifact = await builder.build(ToolBuildRequestedEvent.model_validate(create_build_payload()))

            self.assertEqual(artifact.file_name, "incident_recovery_tool.py")
            self.assertIn("class IncidentRecoveryTool", artifact.code_snapshot)
            self.assertEqual(artifact.metadata_json["toolName"], "incident_recovery_tool")
            self.assertEqual(artifact.metadata_json["generatedSpec"]["displayName"], "Incident Recovery Tool")
            self.assertEqual(artifact.display_name, "Incident Recovery Tool")
            self.assertEqual(artifact.display_description, "Analyzes incident logs and suggests recovery steps.")
            self.assertEqual(artifact.permission_level, 1)
            self.assertEqual(len(llm.requests), 1)

    async def test_builder_repairs_llm_code_after_validation_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            llm = SequentialFakeLlmClient([create_llm_json(), create_llm_json()])
            builder = ToolBuilder(llm_client=llm, storage_root=Path(tmpdir))

            fake_tool_class = type("IncidentRecoveryTool", (), {"name": "incident_recovery_tool"})
            validation_error = ToolCreationError("validation_failed", "Missing execute method.")
            with patch("src.tool_build.builder.validate_draft_tool", side_effect=[validation_error, fake_tool_class]), \
                patch("src.tool_build.builder.run_tool_sandbox_gate_for_artifact", new=AsyncMock(return_value={"success": True})), \
                patch("src.tool_build.builder.activate_tool_artifact", return_value=False):
                artifact = await builder.build(ToolBuildRequestedEvent.model_validate(create_build_payload()))

            self.assertEqual(artifact.file_name, "incident_recovery_tool.py")
            self.assertEqual(len(llm.requests), 2)
            self.assertIn("Missing execute method.", llm.requests[1].messages[0].text)

    async def test_builder_fails_after_repair_attempts_are_exhausted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            llm = SequentialFakeLlmClient([create_llm_json(), create_llm_json(), create_llm_json()])
            builder = ToolBuilder(llm_client=llm, storage_root=Path(tmpdir))

            validation_error = ToolCreationError("validation_failed", "Still invalid.")
            with patch("src.tool_build.builder.validate_draft_tool", side_effect=validation_error):
                with self.assertRaisesRegex(Exception, "Still invalid."):
                    await builder.build(ToolBuildRequestedEvent.model_validate(create_build_payload()))

            self.assertEqual(len(llm.requests), 3)

    async def test_processor_publishes_failed_event_on_build_timeout(self):
        publisher = AsyncMock()
        processor = ToolBuildProcessor(publisher=publisher, builder=SlowBuilder())

        with patch("src.tool_build.processor.settings.CORE_TOOL_BUILD_RUN_TIMEOUT_SECONDS", 0.01):
            await processor.process_message(create_build_payload())

        failed = publisher.publish.await_args_list[-1].args[1]
        self.assertEqual(failed.event_type, "TOOL_BUILD_FAILED")
        self.assertEqual(failed.code, "TOOL_BUILD_TIMEOUT")

    async def test_build_request_contract_requires_api_fields_and_no_tool_id(self):
        event = ToolBuildRequestedEvent.model_validate(create_build_payload())

        dumped = event.model_dump(mode="json", by_alias=True)

        self.assertEqual(dumped["eventType"], "TOOL_BUILD_REQUESTED")
        self.assertEqual(dumped["approvedByProjectMemberId"], 5)
        self.assertEqual(dumped["requestedAt"], "2026-05-08T14:10:00")
        self.assertIn("approvedPlan", dumped)
        self.assertNotIn("toolId", dumped)

        invalid_payload = dict(create_build_payload())
        invalid_payload.pop("requestedAt")
        with self.assertRaises(ValidationError):
            ToolBuildRequestedEvent.model_validate(invalid_payload)

    async def test_completed_event_contract_uses_optional_artifact_fields_and_no_tool_id(self):
        completed = ToolBuildCompletedEvent(
            runId="build-run-1",
            eventSequence=3,
            projectId=1,
            chatSessionId=2,
            toolPlanId=10,
            artifact=ToolArtifactPayload(fileName="incident_tool.py"),
        )

        dumped = completed.model_dump(mode="json", by_alias=True)

        self.assertEqual(dumped["eventType"], "TOOL_BUILD_COMPLETED")
        self.assertEqual(dumped["eventSequence"], 3)
        self.assertEqual(dumped["artifact"]["fileName"], "incident_tool.py")
        self.assertIsNone(dumped["artifact"]["moduleName"])
        self.assertIsNone(dumped["artifact"]["metadataJson"])
        self.assertNotIn("toolId", dumped)

    async def test_failed_event_contract_includes_event_sequence_and_no_tool_id(self):
        failed = ToolBuildFailedEvent(
            runId="build-run-1",
            eventSequence=4,
            projectId=1,
            chatSessionId=2,
            toolPlanId=10,
            code="VALIDATION_FAILED",
            message="Tool validation failed.",
        )

        dumped = failed.model_dump(mode="json", by_alias=True)

        self.assertEqual(dumped["eventType"], "TOOL_BUILD_FAILED")
        self.assertEqual(dumped["eventSequence"], 4)
        self.assertEqual(dumped["code"], "VALIDATION_FAILED")
        self.assertNotIn("toolId", dumped)


def create_build_payload():
    return {
        "eventType": "TOOL_BUILD_REQUESTED",
        "runId": "build-run-1",
        "projectId": 1,
        "chatSessionId": 2,
        "toolPlanId": 10,
        "planGroupId": 4,
        "approvedByProjectMemberId": 5,
        "requestedAt": "2026-05-08T14:10:00",
        "approvedPlan": {
            "rawMarkdown": "## Incident recovery tool",
            "structuredPlanJson": {"version": 1, "blocks": []},
            "planSnapshot": {
                "schemaVersion": 1,
                "planVersion": 1,
                "title": "Incident Recovery Tool",
                "summary": "Analyze incident logs.",
                "blocks": [],
                "inputs": [],
                "outputs": [],
                "constraints": [],
            },
        },
    }


def create_artifact() -> ToolArtifactPayload:
    return ToolArtifactPayload(
        fileName="incident_tool.py",
        moduleName="project__incident_tool",
        artifactPath="projects/1/incident_tool.py",
        codeSnapshot="print('ok')",
        metadataJson={"toolName": "incident_tool"},
    )


def create_llm_json() -> str:
    code = '''from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult


class IncidentRecoveryInput(BaseModel):
    log_text: str = Field(default="", description="Incident log text")


class IncidentRecoveryTool(BaseTool):
    name = "incident_recovery_tool"
    description = "Summarizes incident logs and suggests recovery steps."
    input_model = IncidentRecoveryInput
    permission_level = 1

    async def execute(self, arguments: IncidentRecoveryInput, context: ToolExecutionContext) -> ToolResult:
        text = arguments.log_text.strip()
        if not text:
            return ToolResult(output="No incident log text was provided.", is_error=True)
        return ToolResult(output={"summary": text[:120], "nextSteps": ["Review recent errors", "Escalate if repeated"]})
'''
    import json

    return json.dumps(
        {
            "toolName": "incident_recovery_tool",
            "fileName": "incident_recovery_tool.py",
            "moduleName": "incident_recovery_tool",
            "displayName": "Incident Recovery Tool",
            "displayDescription": "Analyzes incident logs and suggests recovery steps.",
            "permissionLevel": 1,
            "pythonCode": code,
            "metadataJson": {
                "inputs": ["log_text"],
                "outputs": ["summary", "nextSteps"],
                "constraints": [],
            },
        }
    )


if __name__ == "__main__":
    unittest.main()
