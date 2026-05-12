import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.engine.stream_events import (
    AssistantTurnComplete,
    ToolExecutionCompleted,
)
from theseus_engine.models.messages import (
    ConversationMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from theseus_engine.tools.core.base_tools import (
    BaseTool,
    ToolExecutionContext,
    ToolRegistry,
    ToolResult,
)
from theseus_engine.wrappers.hooks.theseus_hook_executor import HookEvent
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    UsageSnapshot,
)


class EchoInput(BaseModel):
    message: str = ""


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo test tool"
    input_model = EchoInput

    async def execute(
        self, arguments: EchoInput, context: ToolExecutionContext
    ) -> ToolResult:
        return ToolResult(output=arguments.message or "original")


class RaisingTool(EchoTool):
    async def execute(
        self, arguments: EchoInput, context: ToolExecutionContext
    ) -> ToolResult:
        raise RuntimeError("boom")


class PermissionChecker:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed

    def evaluate(self, *args, **kwargs):
        return SimpleNamespace(
            allowed=self.allowed,
            requires_confirmation=False,
            reason="권한이 없습니다.",
        )


class CapturingHook:
    def __init__(self, *, post_output: str | None = None) -> None:
        self.calls = []
        self.post_output = post_output

    async def execute(self, event, payload):
        self.calls.append((event, dict(payload)))
        if event == HookEvent.POST_TOOL_USE and self.post_output is not None:
            payload["tool_output"] = self.post_output
        return SimpleNamespace(blocked=False, reason="")


class ScriptedClient:
    def __init__(self, *, use_tool: bool = True) -> None:
        self.requests = []
        self.use_tool = use_tool

    async def stream_message(self, request):
        self.requests.append(request)
        if self.use_tool and len(self.requests) == 1:
            message = ConversationMessage(
                role="assistant",
                content=[
                    ToolUseBlock(
                        id="toolu_test",
                        name="echo",
                        input={"message": "original"},
                    )
                ],
            )
            usage = UsageSnapshot(input_tokens=3, output_tokens=5)
        else:
            message = ConversationMessage(
                role="assistant",
                content=[TextBlock(text="done")],
            )
            usage = UsageSnapshot(input_tokens=7, output_tokens=11)
        yield ApiMessageCompleteEvent(message=message, usage=usage)


def make_registry(tool: BaseTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(tool)
    return registry


def find_tool_result(messages: list[ConversationMessage]) -> ToolResultBlock:
    for message in reversed(messages):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                return block
    raise AssertionError("tool result block not found")


class QueryEngineExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_rbac_denial_skips_pre_tool_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = CapturingHook()
            engine = QueryEngine(
                api_client=ScriptedClient(),
                tool_registry=make_registry(EchoTool()),
                permission_checker=PermissionChecker(allowed=False),
                cwd=Path(tmp),
                model="test-model",
                system_prompt="test",
                hook_executor=hook,
            )

            events = [event async for event in engine.submit_message("run")]

        completed = [
            event for event in events if isinstance(event, ToolExecutionCompleted)
        ]
        self.assertEqual(len(completed), 1)
        self.assertTrue(completed[0].is_error)
        self.assertFalse(
            any(event == HookEvent.PRE_TOOL_USE for event, _ in hook.calls)
        )

    async def test_single_tool_exception_becomes_tool_error_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = ScriptedClient()
            engine = QueryEngine(
                api_client=client,
                tool_registry=make_registry(RaisingTool()),
                permission_checker=PermissionChecker(),
                cwd=Path(tmp),
                model="test-model",
                system_prompt="test",
            )

            events = [event async for event in engine.submit_message("run")]

        completed = [
            event for event in events if isinstance(event, ToolExecutionCompleted)
        ]
        self.assertEqual(len(completed), 1)
        self.assertTrue(completed[0].is_error)
        self.assertIn("도구 실행 실패", completed[0].output)
        result_block = find_tool_result(client.requests[1].messages)
        self.assertEqual(result_block.content, completed[0].output)

    async def test_post_hook_output_is_sent_to_event_and_next_model_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = ScriptedClient()
            engine = QueryEngine(
                api_client=client,
                tool_registry=make_registry(EchoTool()),
                permission_checker=PermissionChecker(),
                cwd=Path(tmp),
                model="test-model",
                system_prompt="test",
                hook_executor=CapturingHook(post_output="mutated"),
            )

            events = [event async for event in engine.submit_message("run")]

        completed = [
            event for event in events if isinstance(event, ToolExecutionCompleted)
        ]
        self.assertEqual(completed[0].output, "mutated")
        result_block = find_tool_result(client.requests[1].messages)
        self.assertEqual(result_block.content, "mutated")

    async def test_total_usage_accumulates_on_assistant_turn_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = QueryEngine(
                api_client=ScriptedClient(use_tool=False),
                tool_registry=ToolRegistry(),
                permission_checker=PermissionChecker(),
                cwd=Path(tmp),
                model="test-model",
                system_prompt="test",
            )

            events = [event async for event in engine.submit_message("hello")]

        self.assertTrue(any(isinstance(e, AssistantTurnComplete) for e in events))
        self.assertEqual(engine.total_usage.input_tokens, 7)
        self.assertEqual(engine.total_usage.output_tokens, 11)
        self.assertEqual(engine.total_usage.prompt_tokens, 7)
        self.assertEqual(engine.total_usage.completion_tokens, 11)


if __name__ == "__main__":
    unittest.main()
