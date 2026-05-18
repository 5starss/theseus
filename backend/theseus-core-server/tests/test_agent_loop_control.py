from __future__ import annotations

import unittest

from theseus_engine.engine.agent_loop_control import should_auto_continue_after_assistant


class AgentLoopControlTest(unittest.TestCase):
    def test_agent_pending_action_continues_once(self) -> None:
        self.assertTrue(
            should_auto_continue_after_assistant(
                final_text="먼저 코드를 정밀하게 읽겠습니다.",
                stop_reason=None,
                tool_call_count=0,
                auto_continue_count=0,
                has_available_tools=True,
                mode="AGENT",
            )
        )

    def test_ask_mode_does_not_auto_continue(self) -> None:
        self.assertFalse(
            should_auto_continue_after_assistant(
                final_text="먼저 코드를 정밀하게 읽겠습니다.",
                stop_reason=None,
                tool_call_count=0,
                auto_continue_count=0,
                has_available_tools=True,
                mode="ASK",
            )
        )

    def test_user_decision_request_does_not_continue(self) -> None:
        self.assertFalse(
            should_auto_continue_after_assistant(
                final_text="진행해도 될까요?",
                stop_reason=None,
                tool_call_count=0,
                auto_continue_count=0,
                has_available_tools=True,
                mode="AGENT",
            )
        )

    def test_provider_length_stop_reasons_continue(self) -> None:
        for stop_reason in ("length", "max_tokens", "model_length", "token_limit", "incomplete"):
            with self.subTest(stop_reason=stop_reason):
                self.assertTrue(
                    should_auto_continue_after_assistant(
                        final_text="",
                        stop_reason=stop_reason,
                        tool_call_count=0,
                        auto_continue_count=0,
                        has_available_tools=True,
                        mode="AGENT",
                    )
                )


if __name__ == "__main__":
    unittest.main()
