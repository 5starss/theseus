from __future__ import annotations

import unittest

from src.tool_plan.display_markdown import build_plan_display_markdown


class PlanDisplayMarkdownTest(unittest.TestCase):
    def test_execution_spec_permission_level_is_visible(self) -> None:
        markdown = build_plan_display_markdown(
            {
                "title": "시간 조회 툴 생성",
                "summary": "시스템 시간 조회 도구를 생성합니다.",
                "blocks": [
                    {
                        "title": "get_system_time 구현",
                        "content": "Problem: 시간 조회 도구가 없음",
                    }
                ],
                "executionSpec": {
                    "tool_name": "get_system_time",
                    "permissionLevel": 1,
                    "permission_rationale": "표준 라이브러리 기반 읽기 전용 시간 조회",
                    "validation_strategy": "core_sandbox_gate",
                },
                "verification": {},
            }
        )

        self.assertIn("권한 레벨: `1`", markdown)
        self.assertIn("표준 라이브러리 기반 읽기 전용 시간 조회", markdown)


if __name__ == "__main__":
    unittest.main()
