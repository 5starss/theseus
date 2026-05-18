from __future__ import annotations

import unittest

from theseus_engine.tools.tool_repair import (
    ToolRepairFailure,
    classify_repair_failure,
)


class ToolRepairClassificationTest(unittest.TestCase):
    def test_missing_module_is_not_tool_name_conflict(self) -> None:
        message = (
            "생성된 Tool 파일을 직접 실행하지 않고 Core sandbox gate에서 "
            "컴파일/import/구조를 검증하는 중 실패했습니다. "
            "sandbox 원인=sandbox_missing_dependency, 누락 모듈=['psutil']. "
            "No module named 'psutil'"
        )

        failure = ToolRepairFailure(
            stage="sandbox_failed",
            code="SANDBOX_FAILED",
            message=message,
        )

        self.assertEqual("SANDBOX_MISSING_DEPENDENCY", failure.code)
        self.assertFalse(failure.is_tool_name_conflict)
        self.assertTrue(failure.is_dependency_failure)
        self.assertTrue(failure.blocks_automatic_retry)

    def test_real_artifact_name_collision_still_classifies_as_conflict(self) -> None:
        message = (
            "이미 존재하는 Tool 파일명입니다. "
            "toolName=cpu_resource_monitor, "
            "moduleName=cpu_resource_monitor_tool, "
            "fileName=cpu_resource_monitor_tool.py."
        )

        self.assertEqual(
            "TOOL_NAME_CONFLICT",
            classify_repair_failure("TOOL_NAME_CONFLICT", message),
        )


if __name__ == "__main__":
    unittest.main()
