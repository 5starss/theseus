"""Helpers for standalone PLAN phase auto-progression."""

from __future__ import annotations


PLAN_EXECUTION_COMPLETE_MARKERS: tuple[str, ...] = (
    "plan complete",
    "all steps complete",
    "execution complete",
)

PLAN_VERIFICATION_COMPLETE_MARKERS: tuple[str, ...] = (
    "verification complete",
    "검증 완료",
    "검증완료",
)

PLAN_VERIFICATION_PROMPT = (
    "Verify the executed plan now. Run relevant read-only checks and tests "
    "if needed, review the completed work against the approved plan, then "
    "return the structured verification summary. End the final response with "
    '"Verification complete."'
)

PLAN_CONTINUE_PROMPT = "Continue. Execute the next step immediately."
PLAN_TOOL_ERROR_PROMPT = "A tool error occurred. Analyze and retry."


def contains_execution_complete(text: str) -> bool:
    """Return whether assistant text signals PLAN execution completion."""
    lower = text.lower()
    return any(marker in lower for marker in PLAN_EXECUTION_COMPLETE_MARKERS)


def contains_verification_complete(text: str) -> bool:
    """Return whether assistant text signals PLAN verification completion."""
    lower = text.lower()
    return any(marker in lower for marker in PLAN_VERIFICATION_COMPLETE_MARKERS)
