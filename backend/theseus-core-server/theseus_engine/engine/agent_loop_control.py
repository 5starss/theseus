from __future__ import annotations

from theseus_engine.engine.loop_decision import (
    AGENT_AUTO_CONTINUE_MAX,
    AUTO_CONTINUE_PROMPT,
    LoopDecisionContext,
    classify_loop_continuation,
    read_non_negative_int_env,
)


def should_auto_continue_after_assistant(
    *,
    final_text: str,
    stop_reason: str | None,
    tool_call_count: int,
    auto_continue_count: int,
    has_available_tools: bool,
    mode: str,
) -> bool:
    """Compatibility wrapper for older callers/tests."""

    decision = classify_loop_continuation(
        LoopDecisionContext(
            mode=mode,
            stop_reason=stop_reason,
            assistant_text=final_text,
            tool_call_count=tool_call_count,
            auto_continue_count=auto_continue_count,
            available_tools=has_available_tools,
            max_auto_continue=AGENT_AUTO_CONTINUE_MAX,
        )
    )
    return decision.should_resume
