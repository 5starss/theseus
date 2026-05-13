import asyncio
from datetime import datetime, timezone

from src.tool_build.builder import ToolBuildError
from src.tool_build.processor import ToolBuildProcessor
from src.tool_build.schemas import ToolBuildFailedEvent, ToolBuildRequestedEvent


class FakePublisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, key, event) -> None:
        self.events.append((key, event))


class FailingBuilder:
    async def build(self, event, *, progress_callback=None, chunk_callback=None):
        raise ToolBuildError(
            "SANDBOX_FAILED",
            (
                "Sandbox result.json was not produced. "
                "(errorType=result_missing, exitCode=1, "
                "timedOut=False, resourceLimited=False)"
            ),
        )


def _build_event() -> ToolBuildRequestedEvent:
    return ToolBuildRequestedEvent.model_validate(
        {
            "eventType": "TOOL_BUILD_REQUESTED",
            "runId": "sandbox-failure-test-run",
            "projectId": 1,
            "chatSessionId": 2,
            "toolPlanId": 3,
            "planGroupId": 4,
            "approvedByProjectMemberId": 5,
            "approvedPlan": {
                "rawMarkdown": "## Test",
                "structuredPlanJson": {},
                "planSnapshot": {"blocks": []},
            },
            "requestedAt": datetime.now(timezone.utc).isoformat(),
        }
    )


async def main() -> None:
    publisher = FakePublisher()
    processor = ToolBuildProcessor(
        publisher=publisher,
        builder=FailingBuilder(),
        checkpoint_repo_factory=None,
    )
    await processor.process_build(_build_event())

    failed_events = [
        event for _, event in publisher.events
        if isinstance(event, ToolBuildFailedEvent)
    ]
    assert len(failed_events) == 1
    failed = failed_events[0]
    assert failed.code == "SANDBOX_FAILED"
    assert "errorType=result_missing" in failed.message
    assert "exitCode=1" in failed.message
    assert "timedOut=False" in failed.message
    assert "resourceLimited=False" in failed.message
    print("tool_build_sandbox_failure: ok")


if __name__ == "__main__":
    asyncio.run(main())
