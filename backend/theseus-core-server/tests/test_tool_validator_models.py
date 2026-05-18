from __future__ import annotations

import textwrap
import unittest

from theseus_engine.tools.core.tool_factory import ToolValidator


class ToolValidatorModelNamingTest(unittest.TestCase):
    def test_helper_output_models_are_allowed(self) -> None:
        code = textwrap.dedent(
            """
            from typing import List
            from pydantic import BaseModel
            from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

            class CPUMonitorInput(BaseModel):
                top_n: int = 5

            class ProcessInfo(BaseModel):
                pid: int
                name: str

            class CPUStatsOutput(BaseModel):
                top_processes: List[ProcessInfo]

            class CPUMonitorTool(BaseTool):
                name: str = "cpu_monitor"
                description: str = "Collects CPU metrics."
                input_model: type[BaseModel] = CPUMonitorInput
                permission_level: int = 2

                async def execute(self, arguments: CPUMonitorInput, context: ToolExecutionContext) -> ToolResult:
                    output = CPUStatsOutput(top_processes=[])
                    return ToolResult(output=output.model_dump())
            """
        )

        ok, message = ToolValidator.validate_code(code)

        self.assertTrue(ok, message)

    def test_actual_input_model_still_has_naming_rule(self) -> None:
        code = textwrap.dedent(
            """
            from pydantic import BaseModel
            from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

            class RandomArgs(BaseModel):
                value: int = 1

            class ExampleTool(BaseTool):
                name: str = "example_tool"
                description: str = "Example."
                input_model: type[BaseModel] = RandomArgs
                permission_level: int = 1

                async def execute(self, arguments: RandomArgs, context: ToolExecutionContext) -> ToolResult:
                    return ToolResult(output="ok")
            """
        )

        ok, message = ToolValidator.validate_code(code)

        self.assertFalse(ok)
        self.assertIn("Input model for 'ExampleTool'", message)


if __name__ == "__main__":
    unittest.main()
