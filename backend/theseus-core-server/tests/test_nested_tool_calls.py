from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, Field

from theseus_engine.engine.query_engine import QueryContext, _execute_tool_call
from theseus_engine.tools.core.base_tools import (
    BaseTool,
    SystemRebootTool,
    ToolExecutionContext,
    ToolRegistry,
    ToolResult,
)


class _AllowPermissionChecker:
    def evaluate(self, *args, **kwargs):
        del args, kwargs
        return SimpleNamespace(
            allowed=True,
            requires_confirmation=False,
            reason="",
        )


class _EmptyInput(BaseModel):
    pass


class _DetailInput(BaseModel):
    value: str = Field(default="ok")


class _DetailTool(BaseTool):
    name = "detail_tool"
    description = "Returns nested detail data."
    input_model = _DetailInput
    permission_level = 1

    async def execute(self, arguments: _DetailInput, context: ToolExecutionContext) -> ToolResult:
        del context
        return ToolResult(output={"detail": arguments.value, "items": [1, 2, 3]})


class _ParentInput(BaseModel):
    value: str = Field(default="parent")


class _ParentTool(BaseTool):
    name = "parent_tool"
    description = "Calls detail_tool through ToolExecutionContext."
    input_model = _ParentInput
    permission_level = 1

    async def execute(self, arguments: _ParentInput, context: ToolExecutionContext) -> ToolResult:
        nested = await context.call_tool("detail_tool", {"value": arguments.value})
        nested_payload = json.loads(nested.output) if not nested.is_error else {"error": nested.output}
        return ToolResult(
            output={
                "nested_error": nested.is_error,
                "nested": nested_payload,
            }
        )


class _SelfCallingTool(BaseTool):
    name = "self_tool"
    description = "Attempts to call itself."
    input_model = _EmptyInput
    permission_level = 1

    async def execute(self, arguments: _EmptyInput, context: ToolExecutionContext) -> ToolResult:
        del arguments
        return await context.call_tool("self_tool")


class _DuplicateParentTool(BaseTool):
    name = "duplicate_parent_tool"
    description = "Attempts the same nested call twice."
    input_model = _EmptyInput
    permission_level = 1

    async def execute(self, arguments: _EmptyInput, context: ToolExecutionContext) -> ToolResult:
        del arguments
        first = await context.call_tool("detail_tool", {"value": "same"})
        second = await context.call_tool("detail_tool", {"value": "same"})
        return ToolResult(
            output={
                "first_error": first.is_error,
                "second_error": second.is_error,
                "second_output": second.output,
            }
        )


class _DangerParentTool(BaseTool):
    name = "danger_parent_tool"
    description = "Attempts to call a blocked nested tool."
    input_model = _EmptyInput
    permission_level = 1

    async def execute(self, arguments: _EmptyInput, context: ToolExecutionContext) -> ToolResult:
        del arguments
        return await context.call_tool("system_reboot", {"reason": "test"})


def _query_context(registry: ToolRegistry, *, metadata: dict[str, object] | None = None) -> QueryContext:
    return QueryContext(
        api_client=object(),
        tool_registry=registry,
        permission_checker=_AllowPermissionChecker(),
        cwd=Path.cwd(),
        model="test-model",
        system_prompt="test",
        max_tokens=1000,
        tool_metadata=metadata or {},
    )


class NestedToolCallTests(unittest.TestCase):
    def test_context_without_invoker_returns_error_result(self) -> None:
        result = asyncio.run(
            ToolExecutionContext(cwd=Path.cwd()).call_tool("detail_tool")
        )

        self.assertTrue(result.is_error)
        self.assertIn("Nested tool calls are not available", result.output)

    def test_parent_tool_can_call_active_detail_tool(self) -> None:
        registry = ToolRegistry()
        registry.register(_ParentTool())
        registry.register(_DetailTool())

        executed = asyncio.run(
            _execute_tool_call(
                _query_context(registry),
                "parent_tool",
                "toolu_parent",
                {"value": "cpu"},
            )
        )

        self.assertFalse(executed.result.is_error)
        payload = json.loads(executed.result.content)
        self.assertFalse(payload["nested_error"])
        self.assertEqual(payload["nested"]["detail"], "cpu")
        self.assertEqual(payload["nested"]["items"], [1, 2, 3])
        nested_events = executed.metadata.get("nestedToolCalls")
        self.assertEqual(len(nested_events), 2)
        self.assertEqual(nested_events[0]["type"], "ToolExecutionStarted")
        self.assertEqual(nested_events[0]["metadata"]["parentToolName"], "parent_tool")
        self.assertTrue(nested_events[0]["metadata"]["nested"])

    def test_recursive_nested_tool_call_is_blocked(self) -> None:
        registry = ToolRegistry()
        registry.register(_SelfCallingTool())

        executed = asyncio.run(
            _execute_tool_call(
                _query_context(registry),
                "self_tool",
                "toolu_self",
                {},
            )
        )

        self.assertTrue(executed.result.is_error)
        self.assertIn("recursive call", executed.result.content)

    def test_nested_tool_depth_limit_is_blocked(self) -> None:
        registry = ToolRegistry()
        registry.register(_ParentTool())
        registry.register(_DetailTool())

        executed = asyncio.run(
            _execute_tool_call(
                _query_context(registry, metadata={"nested_tool_max_depth": 0}),
                "parent_tool",
                "toolu_parent",
                {"value": "cpu"},
            )
        )

        self.assertFalse(executed.result.is_error)
        payload = json.loads(executed.result.content)
        self.assertTrue(payload["nested_error"])
        self.assertIn("maximum nested tool depth", payload["nested"]["error"])

    def test_duplicate_same_tool_and_arguments_is_blocked(self) -> None:
        registry = ToolRegistry()
        registry.register(_DuplicateParentTool())
        registry.register(_DetailTool())

        executed = asyncio.run(
            _execute_tool_call(
                _query_context(registry),
                "duplicate_parent_tool",
                "toolu_duplicate",
                {},
            )
        )

        self.assertFalse(executed.result.is_error)
        payload = json.loads(executed.result.content)
        self.assertFalse(payload["first_error"])
        self.assertTrue(payload["second_error"])
        self.assertIn("repeated same tool and arguments", payload["second_output"])

    def test_blocked_tool_name_cannot_run_as_nested_call(self) -> None:
        registry = ToolRegistry()
        registry.register(_DangerParentTool())
        registry.register(SystemRebootTool())

        executed = asyncio.run(
            _execute_tool_call(
                _query_context(registry),
                "danger_parent_tool",
                "toolu_danger",
                {},
            )
        )

        self.assertTrue(executed.result.is_error)
        self.assertIn("not allowed to run as a nested call", executed.result.content)


if __name__ == "__main__":
    unittest.main()
