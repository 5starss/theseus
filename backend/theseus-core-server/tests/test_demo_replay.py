from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.demo_replay import (
    build_tool_plan_result_from_replay,
    chat_replay_stream_events,
    find_chat_replay,
    find_tool_plan_replay,
)
from src.tool_plan.schemas import ToolPlanRequestedEvent


class DemoReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_enabled = settings.THESEUS_DEMO_REPLAY_ENABLED
        self._old_path = settings.THESEUS_DEMO_REPLAY_PATH

    def tearDown(self) -> None:
        settings.THESEUS_DEMO_REPLAY_ENABLED = self._old_enabled
        settings.THESEUS_DEMO_REPLAY_PATH = self._old_path

    def _enable_replay(self, text: str) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "replays.yaml"
        path.write_text(text, encoding="utf-8")
        settings.THESEUS_DEMO_REPLAY_ENABLED = True
        settings.THESEUS_DEMO_REPLAY_PATH = str(path)

    def test_chat_replay_matches_keyword_and_normalizes_tool_events(self) -> None:
        self._enable_replay(
            """
chat_replays:
  - id: chat-demo
    modes: [AGENT]
    match:
      contains_any: ["모니터링 툴 사용"]
    answer:
      beforeTools: "시작합니다."
      afterTools: "완료했습니다."
    toolStack:
      - label: "monitor"
        toolName: monitor_tool
        toolUseId: tool-1
        toolInput:
          symbol: SSAFY
        started:
          message: "monitor_tool 실행"
        completed:
          output: "정상"
"""
        )

        replay = find_chat_replay(
            prompt="신입사원 모니터링 툴 사용",
            mode="AGENT",
            user_id=1,
            project_id=10,
        )

        self.assertIsNotNone(replay)
        events = chat_replay_stream_events(replay or {})
        self.assertEqual(
            ["chunk", "status", "tool_result", "chunk"],
            [item["event"] for item in events],
        )
        self.assertEqual("monitor_tool", events[1]["data"]["tool_name"])
        self.assertEqual("tool-1", events[2]["data"]["tool_use_id"])
        self.assertEqual("완료했습니다.", events[3]["data"]["content"])

    def test_chat_replay_keeps_low_level_events_compatible(self) -> None:
        self._enable_replay(
            """
chat_replays:
  - id: chat-events-demo
    modes: [AGENT]
    match:
      contains_any: ["프론트 변경 툴 실패"]
    events:
      - type: chunk
        content: "시도합니다."
      - type: tool_result
        toolName: frontend_tool
        toolUseId: tool-2
        output: "실패"
        isError: true
"""
        )

        replay = find_chat_replay(
            prompt="프론트 변경 툴 실패",
            mode="AGENT",
            user_id=1,
            project_id=10,
        )
        events = chat_replay_stream_events(replay or {})

        self.assertEqual(["chunk", "tool_result"], [item["event"] for item in events])
        self.assertTrue(events[1]["data"]["is_error"])

    def test_replay_remote_policy_limits_matches(self) -> None:
        self._enable_replay(
            """
chat_replays:
  - id: agent-remote-demo
    modes: [AGENT]
    match:
      remote: required
      contains_any: ["모니터링 툴 사용"]
    answer:
      afterTools: "remote ok"
plan_replays:
  - id: plan-local-demo
    modes: [PLAN]
    match:
      remote: none
      contains_any: ["휴가 전 플랜 생성"]
    result:
      rawMarkdown: "## local plan"
      structuredPlanJson:
        goal: "local"
      planSnapshot:
        blocks: []
"""
        )

        self.assertIsNone(
            find_chat_replay(
                prompt="모니터링 툴 사용",
                mode="AGENT",
                user_id=1,
                project_id=10,
            )
        )
        self.assertIsNotNone(
            find_chat_replay(
                prompt="모니터링 툴 사용",
                mode="AGENT",
                user_id=1,
                project_id=10,
                remote_workspace_id=20,
            )
        )

        local_plan_event = ToolPlanRequestedEvent(
            eventType="TOOL_PLAN_REQUESTED",
            runId="run-local-demo",
            projectId=1,
            chatSessionId=2,
            requestedByUserId=3,
            requestedByProjectMemberId=4,
            prompt="휴가 전 플랜 생성",
            requestedAt=datetime.now(timezone.utc),
        )
        remote_plan_event = ToolPlanRequestedEvent(
            eventType="TOOL_PLAN_REQUESTED",
            runId="run-remote-demo",
            projectId=1,
            chatSessionId=2,
            requestedByUserId=3,
            requestedByProjectMemberId=4,
            prompt="휴가 전 플랜 생성",
            remoteWorkspaceId=20,
            requestedAt=datetime.now(timezone.utc),
        )

        self.assertIsNotNone(find_tool_plan_replay(local_plan_event))
        self.assertIsNone(find_tool_plan_replay(remote_plan_event))

    def test_plan_replay_builds_tool_plan_result(self) -> None:
        self._enable_replay(
            """
plan_replays:
  - id: plan-demo
    modes: [PLAN]
    match:
      contains_all: ["휴가", "계획"]
    result:
      rawMarkdown: "## Demo PLAN"
      structuredPlanJson:
        goal: "demo"
        tasks:
          - id: task-1
            title: "Demo task"
      planSnapshot:
        blocks:
          - blockId: task-1
            title: "Demo task"
            content: "Demo"
"""
        )
        event = ToolPlanRequestedEvent(
            eventType="TOOL_PLAN_REQUESTED",
            runId="run-demo",
            projectId=1,
            chatSessionId=2,
            requestedByUserId=3,
            requestedByProjectMemberId=4,
            prompt="휴가 전 계획을 세워줘",
            requestedAt=datetime.now(timezone.utc),
        )

        replay = find_tool_plan_replay(event)
        result = build_tool_plan_result_from_replay(replay or {})

        self.assertIsNotNone(replay)
        self.assertEqual("## Demo PLAN", result.raw_markdown)
        self.assertEqual("demo", result.structured_plan_json["goal"])
        self.assertEqual("task-1", result.plan_snapshot["blocks"][0]["blockId"])


if __name__ == "__main__":
    unittest.main()
