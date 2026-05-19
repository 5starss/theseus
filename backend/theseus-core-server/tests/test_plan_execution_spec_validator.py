from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.tool_plan.execution_spec_validator import validate_execution_spec_if_required
from src.tool_plan.schemas import ToolPlanRequestedEvent


def _event(prompt: str = "배포 후 점검 Tool 만들어줘") -> ToolPlanRequestedEvent:
    return ToolPlanRequestedEvent(
        eventType="TOOL_PLAN_REQUESTED",
        runId="run-1",
        projectId=1,
        chatSessionId=10,
        requestedByUserId=100,
        requestedByProjectMemberId=200,
        prompt=prompt,
        requestedAt=datetime.now(timezone.utc),
    )


class PlanExecutionSpecValidatorTest(unittest.TestCase):
    def test_missing_quality_fields_are_warnings_not_errors(self) -> None:
        plan = {
            "goal": "Docker health check Tool",
            "execution_spec": {
                "steps": [
                    {
                        "step_id": "inspect",
                        "commands": [
                            {
                                "command": (
                                    "docker inspect api "
                                    "--format='Status={{.State.Status}} RestartCount={{.RestartCount}} "
                                    "ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} "
                                    "Health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}'"
                                ),
                                "type": "read_only",
                            }
                        ],
                    }
                ],
            },
        }

        result = validate_execution_spec_if_required(plan, _event(), validation_mode="strict")

        self.assertEqual([], result.errors)
        self.assertTrue(any("failure_policy" in item for item in result.warnings))
        self.assertTrue(any("required_result_fields" in item for item in result.warnings))

    def test_destructive_command_is_hard_error(self) -> None:
        plan = {
            "goal": "restart unhealthy container",
            "execution_spec": {
                "steps": [
                    {
                        "commands": [
                            {
                                "command": "docker restart api",
                                "type": "read_only",
                            }
                        ],
                    }
                ],
            },
        }

        result = validate_execution_spec_if_required(plan, _event(), validation_mode="strict")

        self.assertTrue(result.errors)
        self.assertTrue(any("denied command pattern" in item for item in result.errors))

    def test_generated_tool_without_commands_uses_sandbox_gate_default(self) -> None:
        plan = {"goal": "현재 시스템 시간을 알려주는 커스텀 툴 생성"}

        result = validate_execution_spec_if_required(
            plan,
            _event("현재 시스템 시간을 알려주는 Tool 만들고 싶어"),
            validation_mode="strict",
        )

        self.assertEqual([], result.errors)
        self.assertEqual("core_sandbox_gate", plan["execution_spec"]["validation_strategy"])
        self.assertEqual(1, plan["execution_spec"]["permissionLevel"])
        self.assertIn("permission_rationale", plan["execution_spec"])

    def test_generated_tool_missing_permission_level_is_quality_warning(self) -> None:
        plan = {
            "goal": "CPU 모니터링 커스텀 툴 생성",
            "execution_spec": {
                "tool_name": "cpu_monitor",
                "validation_strategy": "core_sandbox_gate",
                "mvp_exclusions": ["write actions"],
                "steps": [],
            },
        }

        result = validate_execution_spec_if_required(
            plan,
            _event("CPU 모니터링 Tool 만들어줘"),
            validation_mode="strict",
        )

        self.assertEqual([], result.errors)
        self.assertTrue(any("permissionLevel" in item for item in result.warnings))


if __name__ == "__main__":
    unittest.main()
