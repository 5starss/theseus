import unittest
from pathlib import Path

from theseus_engine.core.plan_flow import (
    contains_execution_complete,
    contains_verification_complete,
)
from theseus_engine.engine.stream_events import AssistantTextDelta
from theseus_engine.models.state import AgentMode, PlanPhase
from theseus_engine.runner_runtime import EditorRuntime


class FakeStateMachine:
    def __init__(self) -> None:
        self.mode = AgentMode.PLAN
        self.plan_phase = PlanPhase.EXECUTING
        self.plan = "approved plan"

    @property
    def is_plan_drafting(self) -> bool:
        return self.plan_phase == PlanPhase.DRAFTING

    def set_plan_phase(self, phase: PlanPhase) -> None:
        self.plan_phase = phase

    def get_system_prompt(self) -> str:
        return f"prompt:{self.plan_phase.value}"


class FakeEngine:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.messages = []
        self.system_prompts: list[str] = []
        self.plan_drafting_flags: list[bool] = []

    def set_plan_drafting(self, value: bool) -> None:
        self.plan_drafting_flags.append(value)

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompts.append(prompt)

    async def submit_message(self, prompt: str):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            yield AssistantTextDelta("Plan complete.")
            return
        yield AssistantTextDelta(
            "## Verification Results\n"
            "- Tests: PASS\n\n"
            "Verification complete."
        )


class FakeSessions:
    current_name = "default"

    def save(self, name, messages):
        self.saved = (name, list(messages))


def make_runtime() -> tuple[EditorRuntime, FakeEngine, FakeStateMachine]:
    runtime = EditorRuntime.__new__(EditorRuntime)
    runtime.model = "test-model"
    runtime.user_level = 5
    runtime.cwd = Path.cwd()
    runtime.engine = FakeEngine()
    runtime.sm = FakeStateMachine()
    runtime.sessions = FakeSessions()
    runtime.AgentMode = AgentMode
    runtime.PlanPhase = PlanPhase

    async def initialize():
        return []

    runtime.initialize = initialize
    return runtime, runtime.engine, runtime.sm


class RunnerRuntimePlanFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_execution_complete_auto_runs_verification_turn(self):
        runtime, engine, state = make_runtime()

        events = [event async for event in runtime.submit("finish work")]

        self.assertEqual(len(engine.prompts), 2)
        self.assertEqual(engine.prompts[0], "finish work")
        self.assertIn("Verify the executed plan now", engine.prompts[1])
        self.assertEqual(state.plan_phase, PlanPhase.VERIFYING)
        self.assertTrue(
            any(
                event["type"] == "AssistantTextDelta"
                and "Verification complete." in event["text"]
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["type"] == "StatusEvent"
                and "자동 검증" in event["message"]
                for event in events
            )
        )

    def test_plan_flow_completion_markers(self):
        self.assertTrue(contains_execution_complete("Plan complete."))
        self.assertTrue(contains_verification_complete("검증 완료"))


if __name__ == "__main__":
    unittest.main()
