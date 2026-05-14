from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("ALLOWED_ORIGINS", '["http://localhost:3000"]')

from pydantic import BaseModel

from src.history.mapper import to_engine_messages
from src.history.schemas import HistoryMessageRecord
from src.tool_plan import planner as planner_module
from theseus_engine.models.messages import (
    ConversationMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from theseus_engine.wrappers.llm_clients.api_types import ApiMessageRequest
from theseus_engine.wrappers.llm_clients.debug_dump import (
    summarize_api_message_request,
    summarize_openai_params,
)


class DummyInput(BaseModel):
    query: str


class ToolContextDebugSmokeTest(unittest.TestCase):
    def test_existing_custom_tool_context_uses_active_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous = planner_module.PROJECT_CUSTOM_TOOLS_DIR
            try:
                planner_module.PROJECT_CUSTOM_TOOLS_DIR = Path(tmp)
                project_dir = Path(tmp) / "1"
                project_dir.mkdir(parents=True)
                (project_dir / "system_monitor_tool.meta.json").write_text(
                    json.dumps(
                        {
                            "toolName": "system_monitor_tool",
                            "displayName": "System Monitor",
                            "displayDescription": "CPU/RAM/GPU 상태를 조회합니다.",
                            "inputs": {"type": "object", "properties": {}},
                            "outputs": {"type": "object"},
                            "constraints": ["read-only"],
                            "status": "active",
                            "isActive": True,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (project_dir / "inactive_tool.meta.json").write_text(
                    json.dumps(
                        {
                            "toolName": "inactive_tool",
                            "status": "inactive",
                            "isActive": False,
                        }
                    ),
                    encoding="utf-8",
                )

                context = planner_module._existing_custom_tool_context(1)
            finally:
                planner_module.PROJECT_CUSTOM_TOOLS_DIR = previous

        self.assertIn("system_monitor_tool", context)
        self.assertIn("CPU/RAM/GPU", context)
        self.assertNotIn("inactive_tool", context)
        self.assertIn("do not propose creating a duplicate tool", context)

    def test_debug_summary_separates_available_tools_from_tool_history(self) -> None:
        request = ApiMessageRequest(
            model="test-model",
            messages=[
                ConversationMessage.from_user_text("hello"),
                ConversationMessage(
                    role="assistant",
                    content=[
                        TextBlock(text="using a tool"),
                        ToolUseBlock(
                            id="toolu_1",
                            name="system_monitor_tool",
                            input={"detail": True},
                        ),
                    ],
                ),
                ConversationMessage(
                    role="user",
                    content=[
                        ToolResultBlock(
                            tool_use_id="toolu_1",
                            content='{"cpu": 10}',
                        )
                    ],
                ),
            ],
            system_prompt="",
            max_tokens=128,
            tools=[
                {
                    "name": "system_monitor_tool",
                    "description": "Monitor system",
                    "input_schema": DummyInput.model_json_schema(),
                }
            ],
        )

        summary = summarize_api_message_request(request)

        self.assertEqual(summary["availableToolNames"], ["system_monitor_tool"])
        self.assertEqual(summary["toolSchemaCount"], 1)
        self.assertEqual(summary["historyToolUseCount"], 1)
        self.assertEqual(summary["historyToolResultCount"], 1)
        self.assertEqual(summary["historyToolNames"], ["system_monitor_tool"])

    def test_openai_summary_counts_provider_tool_calls_and_results(self) -> None:
        summary = summarize_openai_params(
            {
                "model": "test-model",
                "messages": [
                    {"role": "system", "content": "prompt"},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "toolu_1",
                                "type": "function",
                                "function": {
                                    "name": "system_monitor_tool",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": "toolu_1",
                        "content": "{}",
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "system_monitor_tool",
                            "parameters": {},
                        },
                    }
                ],
            }
        )

        self.assertEqual(summary["toolSchemaCount"], 1)
        self.assertEqual(summary["providerToolCallCount"], 1)
        self.assertEqual(summary["providerToolResultCount"], 1)
        self.assertEqual(summary["providerToolNames"], ["system_monitor_tool"])

    def test_history_mapper_projects_tool_result_json_to_assistant_context(self) -> None:
        record = HistoryMessageRecord(
            messageId=1,
            chatSessionId=10,
            messageOrder=1,
            senderType="SYSTEM",
            messageType="TOOL_RESULT",
            contentType="JSON",
            content=json.dumps(
                {
                    "toolName": "system_monitor_tool",
                    "isError": False,
                    "output": "CPU 10%, RAM 30%",
                },
                ensure_ascii=False,
            ),
            createdAt=datetime.now(),
        )

        messages = to_engine_messages([record])

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].role, "assistant")
        self.assertIn("이전 도구 실행 결과", messages[0].text)
        self.assertIn("system_monitor_tool", messages[0].text)


if __name__ == "__main__":
    unittest.main()
