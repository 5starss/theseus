import os
import sys
import unittest

sys.path.append(os.getcwd())

from theseus_engine.models.state import AgentMode, PlanPhase, TheseusStateMachine
from theseus_engine.engine.stream_events import PlanPhaseTransitionRequested
from theseus_engine.runner_runtime import event_to_json


class PromptAssemblyTests(unittest.TestCase):
    def test_ask_prompt_omits_tool_capability_sections(self) -> None:
        state = TheseusStateMachine(initial_mode=AgentMode.ASK)

        prompt = state.get_system_prompt(available_tools=[])

        self.assertIn("# Current Mode: ASK", prompt)
        self.assertNotIn("# Tool Use Capability", prompt)
        self.assertNotIn("# Theseus RBAC", prompt)
        self.assertNotIn("# create_tool Capability", prompt)

    def test_agent_prompt_uses_only_present_capabilities(self) -> None:
        state = TheseusStateMachine(initial_mode=AgentMode.AGENT)

        prompt = state.get_system_prompt(available_tools=["read_file", "grep"])

        self.assertIn("# Current Mode: AGENT", prompt)
        self.assertIn("# Tool Use Capability", prompt)
        self.assertIn("# Theseus RBAC", prompt)
        self.assertNotIn("# Web Research Capability", prompt)
        self.assertNotIn("# create_tool Capability", prompt)

    def test_plan_executing_includes_create_tool_guidance_when_available(self) -> None:
        state = TheseusStateMachine(initial_mode=AgentMode.PLAN)
        state.plan_phase = PlanPhase.EXECUTING
        state.plan = '{"goal": "create a tool"}'

        prompt = state.get_system_prompt(available_tools=["create_tool", "read_file"])

        self.assertIn("# Current Mode: PLAN — Phase: EXECUTING", prompt)
        self.assertIn("# create_tool Capability", prompt)
        self.assertIn("ToolResult.from_error()", prompt)

    def test_plan_executing_omits_create_tool_guidance_when_unavailable(self) -> None:
        state = TheseusStateMachine(initial_mode=AgentMode.PLAN)
        state.plan_phase = PlanPhase.EXECUTING
        state.plan = '{"goal": "create a tool"}'

        prompt = state.get_system_prompt(available_tools=["read_file"])

        self.assertIn("create_tool is not available in the current", prompt)
        self.assertNotIn("# create_tool Capability", prompt)

    def test_runtime_reminders_are_appended_without_tools(self) -> None:
        state = TheseusStateMachine(initial_mode=AgentMode.PLAN)
        state.plan_phase = PlanPhase.DRAFTING

        prompt = state.get_system_prompt(
            available_tools=[],
            runtime_reminders=["Return only JSON."],
        )

        self.assertIn("# Runtime Reminders", prompt)
        self.assertIn("Return only JSON.", prompt)
        self.assertNotIn("# Tool Use Capability", prompt)

    def test_plan_phase_transition_event_serializes_for_runner(self) -> None:
        event = PlanPhaseTransitionRequested(
            from_phase="Executing",
            to_phase="Verifying",
            reason="done",
            trigger="execution_complete_marker",
        )

        payload = event_to_json(event)

        self.assertEqual(payload["type"], "PlanPhaseTransitionRequested")
        self.assertEqual(payload["from_phase"], "Executing")
        self.assertEqual(payload["to_phase"], "Verifying")


if __name__ == "__main__":
    unittest.main()
