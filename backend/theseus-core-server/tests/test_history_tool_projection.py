from __future__ import annotations

import json
import unittest
from datetime import datetime

from src.history.mapper import to_engine_messages
from src.history.schemas import HistoryMessageRecord


def _history_record(
    *,
    message_id: int = 1,
    sender_type: str = "SYSTEM",
    message_type: str = "SYSTEM_NOTICE",
    content_type: str = "JSON",
    content: str,
) -> HistoryMessageRecord:
    return HistoryMessageRecord(
        messageId=message_id,
        chatSessionId=10,
        messageOrder=message_id,
        senderType=sender_type,
        messageType=message_type,
        contentType=content_type,
        content=content,
        createdAt=datetime.now(),
    )


class HistoryToolProjectionTests(unittest.TestCase):
    def test_system_tool_started_notice_is_not_projected_to_llm_history(self) -> None:
        record = _history_record(
            content=json.dumps(
                {
                    "noticeType": "TOOL_EXECUTION_STARTED",
                    "toolName": "system_health_reporter",
                    "toolUseId": "toolu_1",
                    "status": "started",
                    "toolInput": {"cpu_threshold": 70, "memory_threshold": 70},
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(to_engine_messages([record]), [])

    def test_direct_tool_started_message_is_not_projected_to_llm_history(self) -> None:
        record = _history_record(
            message_type="TOOL_EXECUTION_STARTED",
            content=json.dumps(
                {
                    "toolName": "system_health_reporter",
                    "toolUseId": "toolu_1",
                    "status": "started",
                    "toolInput": {"cpu_threshold": 70, "memory_threshold": 70},
                },
                ensure_ascii=False,
            ),
        )

        self.assertEqual(to_engine_messages([record]), [])

    def test_completed_tool_result_is_projected_as_structured_transcript(self) -> None:
        started = _history_record(
            message_id=1,
            content=json.dumps(
                {
                    "noticeType": "TOOL_EXECUTION_STARTED",
                    "toolName": "system_health_reporter",
                    "toolUseId": "toolu_1",
                    "status": "started",
                    "toolInput": {"cpu_threshold": 70, "memory_threshold": 70},
                },
                ensure_ascii=False,
            ),
        )
        record = _history_record(
            message_id=2,
            content=json.dumps(
                {
                    "noticeType": "TOOL_EXECUTION_COMPLETED",
                    "toolName": "system_health_reporter",
                    "toolUseId": "toolu_1",
                    "status": "completed",
                    "isError": False,
                    "toolInput": {"cpu_threshold": 70, "memory_threshold": 70},
                    "output": "# System Health Report [PASS]",
                },
                ensure_ascii=False,
            ),
        )

        messages = to_engine_messages([started, record])

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "assistant")
        self.assertEqual(messages[0].content[0].type, "tool_use")
        self.assertEqual(messages[0].content[0].name, "system_health_reporter")
        self.assertEqual(messages[0].content[0].input["cpu_threshold"], 70)
        self.assertEqual(messages[1].role, "user")
        self.assertEqual(messages[1].content[0].type, "tool_result")
        self.assertEqual(messages[1].content[0].tool_use_id, "toolu_1")
        self.assertIn("System Health Report", messages[1].content[0].content)

    def test_completed_tool_result_without_started_notice_gets_synthetic_tool_use(self) -> None:
        record = _history_record(
            message_id=2,
            content=json.dumps(
                {
                    "noticeType": "TOOL_EXECUTION_COMPLETED",
                    "toolName": "cpu_monitor",
                    "status": "completed",
                    "isError": False,
                    "toolInput": {"top_n": 5},
                    "output": {"cpu_summary": {"cpu_overall_percent": 1.1}},
                },
                ensure_ascii=False,
            ),
        )

        messages = to_engine_messages([record])

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "assistant")
        self.assertEqual(messages[0].content[0].type, "tool_use")
        self.assertEqual(messages[0].content[0].name, "cpu_monitor")
        self.assertEqual(messages[1].role, "user")
        self.assertEqual(messages[1].content[0].type, "tool_result")
        self.assertIn("cpu_overall_percent", messages[1].content[0].content)

    def test_legacy_tool_execution_text_notice_is_not_projected(self) -> None:
        record = _history_record(
            message_id=3,
            content_type="TEXT",
            content="Tool execution: system_health_reporter started",
        )

        self.assertEqual(to_engine_messages([record]), [])


if __name__ == "__main__":
    unittest.main()
