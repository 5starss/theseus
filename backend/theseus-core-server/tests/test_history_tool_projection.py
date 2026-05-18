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
                    "status": "started",
                    "input": {"cpu_threshold": 70, "memory_threshold": 70},
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
                    "status": "started",
                    "input": {"cpu_threshold": 70, "memory_threshold": 70},
                },
                ensure_ascii=False,
            ),
        )

        self.assertEqual(to_engine_messages([record]), [])

    def test_completed_tool_result_is_projected_to_llm_history(self) -> None:
        record = _history_record(
            message_id=2,
            content=json.dumps(
                {
                    "noticeType": "TOOL_EXECUTION_COMPLETED",
                    "toolName": "system_health_reporter",
                    "status": "completed",
                    "isError": False,
                    "input": {"cpu_threshold": 70, "memory_threshold": 70},
                    "output": "# System Health Report [PASS]",
                },
                ensure_ascii=False,
            ),
        )

        messages = to_engine_messages([record])

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].role, "assistant")
        self.assertIn("이전 도구 실행 결과", messages[0].text)
        self.assertIn("system_health_reporter", messages[0].text)
        self.assertIn("System Health Report", messages[0].text)
        self.assertNotIn("이전 도구 호출", messages[0].text)

    def test_legacy_tool_execution_text_notice_is_not_projected(self) -> None:
        record = _history_record(
            message_id=3,
            content_type="TEXT",
            content="Tool execution: system_health_reporter started",
        )

        self.assertEqual(to_engine_messages([record]), [])


if __name__ == "__main__":
    unittest.main()
