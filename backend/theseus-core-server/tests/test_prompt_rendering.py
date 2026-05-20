from __future__ import annotations

import re
import unittest

from theseus_engine.models.modes import AgentMode, CoordinatorPhase, PlanPhase
from theseus_engine.prompts.builder import build_system_prompt
from theseus_engine.prompts.capabilities import (
    TOOL_USE_CAPABILITY_PROMPT,
    default_tool_names_for_mode,
)
from theseus_engine.prompts.coordinator import (
    COORDINATOR_DECOMPOSE_PROMPT,
    COORDINATOR_DISPATCH_PROMPT,
)
from theseus_engine.prompts.environment import get_environment_section


class PromptRenderingTest(unittest.TestCase):
    def test_plan_drafting_default_tools_do_not_include_bash(self) -> None:
        tools = default_tool_names_for_mode(
            AgentMode.PLAN,
            PlanPhase.DRAFTING,
            None,
        )

        self.assertNotIn("bash", tools)
        self.assertIn("read_file", tools)
        self.assertIn("tool_search", tools)
        self.assertIn("custom_tool_read_source", tools)

    def test_generated_tool_permission_level_exception_is_rendered(self) -> None:
        prompt = build_system_prompt(
            mode=AgentMode.PLAN,
            plan_phase=PlanPhase.DRAFTING,
            available_tools=["read_file", "tool_search"],
        )

        self.assertIn("execution_spec.permissionLevel", prompt)
        self.assertIn("generated tool's required permission level", prompt)
        self.assertIn("not as disclosure of the user's own RBAC level", prompt)
        self.assertIn("Do not omit `execution_spec.permissionLevel`", prompt)
        self.assertIn("It must be a concrete", prompt)
        self.assertIn("review, approval, and RBAC/tool creation", prompt)

    def test_base_prompt_keeps_minimal_analytical_language_neutral_guidance(self) -> None:
        prompts = [
            build_system_prompt(mode=AgentMode.ASK, available_tools=[]),
            build_system_prompt(mode=AgentMode.AGENT, available_tools=[]),
            build_system_prompt(
                mode=AgentMode.PLAN,
                plan_phase=PlanPhase.DRAFTING,
                available_tools=[],
            ),
        ]

        for prompt in prompts:
            with self.subTest(prompt=prompt[:40]):
                self.assertIn("professional, analytical AI agent", prompt)
                self.assertIn("controlled tool workflows", prompt)
                self.assertIn("clear reasoning", prompt)
                self.assertIn("professional, analytical, respectful register", prompt)
                self.assertIn("Follow the user's latest language", prompt)
                self.assertNotIn("# Identity / Product Persona", prompt)
                self.assertNotIn("mythological or philosophical rationale", prompt)

    def test_rendered_core_prompts_do_not_include_language_specific_examples(self) -> None:
        prompts = [
            build_system_prompt(mode=AgentMode.ASK, available_tools=[]),
            build_system_prompt(mode=AgentMode.AGENT, available_tools=[]),
            build_system_prompt(
                mode=AgentMode.PLAN,
                plan_phase=PlanPhase.DRAFTING,
                available_tools=[],
            ),
            build_system_prompt(
                mode=AgentMode.PLAN,
                plan_phase=PlanPhase.WAIT_FOR_REVIEW,
                available_tools=[],
            ),
            build_system_prompt(
                mode=AgentMode.PLAN,
                plan_phase=PlanPhase.EXECUTING,
                available_tools=[],
            ),
            build_system_prompt(
                mode=AgentMode.PLAN,
                plan_phase=PlanPhase.VERIFYING,
                available_tools=[],
            ),
            build_system_prompt(
                mode=AgentMode.COORDINATOR,
                coordinator_phase=CoordinatorPhase.DECOMPOSE,
                available_tools=[],
            ),
            build_system_prompt(
                mode=AgentMode.COORDINATOR,
                coordinator_phase=CoordinatorPhase.DISPATCH,
                available_tools=[],
            ),
        ]

        hangul = re.compile(r"[\uac00-\ud7a3]")
        for prompt in prompts:
            with self.subTest(prompt=prompt[:40]):
                self.assertIsNone(hangul.search(prompt))

    def test_tool_use_prompt_distinguishes_tools_from_shell_commands(self) -> None:
        self.assertIn("use the `glob` tool instead of shell `find` or `ls`", TOOL_USE_CAPABILITY_PROMPT)
        self.assertIn("use the `grep` tool instead of shell `grep` or `rg`", TOOL_USE_CAPABILITY_PROMPT)

    def test_coordinator_decompose_does_not_dispatch_agent_tool(self) -> None:
        self.assertNotIn("call `agent` tool once", COORDINATOR_DECOMPOSE_PROMPT)
        self.assertIn("Do NOT dispatch workers in this phase", COORDINATOR_DECOMPOSE_PROMPT)
        self.assertIn("Call the `agent` tool once", COORDINATOR_DISPATCH_PROMPT)

    def test_environment_date_declares_utc(self) -> None:
        self.assertIn("- Date:", get_environment_section())
        self.assertIn("(UTC)", get_environment_section())

    def test_coordinator_prompt_selection_keeps_dispatch_instruction_in_dispatch_phase(self) -> None:
        prompt = build_system_prompt(
            mode=AgentMode.COORDINATOR,
            coordinator_phase=CoordinatorPhase.DISPATCH,
            available_tools=["agent", "task_output"],
        )

        self.assertIn("Call the `agent` tool once", prompt)


if __name__ == "__main__":
    unittest.main()
