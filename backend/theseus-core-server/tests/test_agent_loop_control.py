from __future__ import annotations

import unittest

from theseus_engine.engine.agent_loop_control import should_auto_continue_after_assistant
from theseus_engine.engine.loop_decision import (
    LoopContinuationDecision,
    LoopDecisionContext,
    classify_loop_continuation,
    decide_loop_continuation,
    parse_semantic_decision_payload,
)


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

    def test_existing_tool_call_prevents_text_based_continue(self) -> None:
        decision = classify_loop_continuation(
            LoopDecisionContext(
                mode="AGENT",
                assistant_text="먼저 파일을 읽겠습니다.",
                tool_call_count=1,
                available_tools=True,
            )
        )

        self.assertEqual("stop", decision.action)
        self.assertEqual("tool_calls_present", decision.reason)

    def test_final_answer_with_action_word_does_not_continue(self) -> None:
        decision = classify_loop_continuation(
            LoopDecisionContext(
                mode="AGENT",
                assistant_text="분석 결과는 다음과 같습니다. 추가 확인은 요청하시면 진행하겠습니다.",
                available_tools=True,
            )
        )

        self.assertEqual("stop", decision.action)
        self.assertEqual("assistant_text_looks_final", decision.reason)

    def test_plan_executing_without_signal_does_not_resume(self) -> None:
        decision = classify_loop_continuation(
            LoopDecisionContext(
                mode="PLAN",
                plan_phase="EXECUTING",
                assistant_text="승인된 계획을 다시 정리했습니다.",
                available_tools=True,
            )
        )

        self.assertEqual("stop", decision.action)

    def test_tool_error_requests_recovery_turn(self) -> None:
        decision = classify_loop_continuation(
            LoopDecisionContext(
                mode="PLAN",
                plan_phase="EXECUTING",
                assistant_text="도구 실행 중 오류가 발생했습니다.",
                tool_error=True,
                available_tools=True,
            )
        )

        self.assertEqual("retry_tool_error", decision.action)
        self.assertTrue(decision.should_resume)

    def test_plan_execution_complete_requests_verification(self) -> None:
        decision = classify_loop_continuation(
            LoopDecisionContext(
                mode="PLAN",
                plan_phase="EXECUTING",
                assistant_text="Execution complete.",
                available_tools=True,
            )
        )

        self.assertEqual("verify", decision.action)
        self.assertTrue(decision.should_resume)

    def test_semantic_low_confidence_continue_can_be_stopped_by_caller(self) -> None:
        fallback = LoopContinuationDecision(
            action="continue",
            reason="assistant_text_has_pending_action_candidate",
            confidence=0.62,
        )
        parsed = parse_semantic_decision_payload(
            '{"action":"continue","confidence":0.41,"reason":"ambiguous"}',
            fallback,
        )

        self.assertIsNotNone(parsed)
        self.assertEqual("continue", parsed.action)
        self.assertLess(parsed.confidence, 0.7)


class AgentLoopSemanticDecisionTest(unittest.IsolatedAsyncioTestCase):
    async def test_low_confidence_semantic_continue_stops(self) -> None:
        async def evaluator(_context, _fallback):
            return LoopContinuationDecision(
                action="continue",
                reason="ambiguous",
                confidence=0.41,
                trigger_signals=("semantic_evaluator",),
            )

        decision = await decide_loop_continuation(
            LoopDecisionContext(
                mode="AGENT",
                assistant_text="먼저 파일을 확인하겠습니다.",
                available_tools=True,
            ),
            semantic_evaluator=evaluator,
            decision_mode="semantic",
        )

        self.assertEqual("stop", decision.action)
        self.assertEqual("semantic_low_confidence", decision.reason)


if __name__ == "__main__":
    unittest.main()
