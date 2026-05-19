from __future__ import annotations

from copy import deepcopy
from typing import Any

PLAN_DRAFT_JSON_SCHEMA_NAME = "theseus_plan_draft"


def plan_draft_json_schema() -> dict[str, Any]:
    """Return the canonical PLAN Draft JSON schema used for structured output.

    The shape intentionally mirrors the JSON example in
    ``theseus_engine.prompts.plan``. It enforces the existing PLAN container
    shape while leaving policy-level requirements to the execution spec
    validator.
    """

    return deepcopy(_PLAN_DRAFT_JSON_SCHEMA)


def plan_draft_response_format() -> dict[str, Any]:
    """OpenAI-compatible ``response_format`` for PLAN Draft JSON output."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": PLAN_DRAFT_JSON_SCHEMA_NAME,
            "schema": plan_draft_json_schema(),
        },
    }


def plan_draft_vllm_extra_body() -> dict[str, Any]:
    """vLLM ``extra_body`` structured output request for PLAN Draft JSON."""

    return {"structured_outputs": {"json": plan_draft_json_schema()}}


_STRING_ARRAY_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string"},
}

_PLAN_DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "required": ["goal", "context", "tasks", "verification", "action_plan"],
    "properties": {
        "goal": {"type": "string"},
        "context": {
            "type": "object",
            "additionalProperties": True,
            "required": ["current_state", "problem_analysis", "affected_files", "risks"],
            "properties": {
                "current_state": {"type": "string"},
                "problem_analysis": {"type": "string"},
                "affected_files": _STRING_ARRAY_SCHEMA,
                "risks": {"type": "string"},
            },
        },
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "tradeoffs": {"type": "string"},
                    "when_to_use": {"type": "string"},
                },
            },
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["id", "parent_id", "title", "description", "target_files", "status"],
                "properties": {
                    "id": {"type": "string"},
                    "parent_id": {"type": ["string", "null"]},
                    "tier": {"type": "string"},
                    "title": {"type": "string"},
                    "problem": {"type": "string"},
                    "solution": {"type": "string"},
                    "target_files": _STRING_ARRAY_SCHEMA,
                    "expected_effect": {"type": "string"},
                    "plan_b": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                    "integration_points": _STRING_ARRAY_SCHEMA,
                    "sequential_dependencies": {"type": "string"},
                },
            },
        },
        "verification": {
            "type": "object",
            "additionalProperties": True,
            "required": ["test_commands", "manual_checks", "success_criteria"],
            "properties": {
                "test_commands": _STRING_ARRAY_SCHEMA,
                "manual_checks": _STRING_ARRAY_SCHEMA,
                "success_criteria": {"type": "string"},
            },
        },
        "execution_spec": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "tool_name": {"type": "string"},
                "permissionLevel": {"type": "integer", "minimum": 1, "maximum": 5},
                "permission_rationale": {"type": "string"},
                "validation_strategy": {"type": "string"},
                "mvp_scope": _STRING_ARRAY_SCHEMA,
                "mvp_exclusions": _STRING_ARRAY_SCHEMA,
                "status_values": _STRING_ARRAY_SCHEMA,
                "implementation_constraints": _STRING_ARRAY_SCHEMA,
                "inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "required": {"type": "boolean"},
                            "description": {"type": "string"},
                        },
                    },
                },
                "outputs": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "format": {"type": "string"},
                        "required_result_fields": _STRING_ARRAY_SCHEMA,
                    },
                },
                "command_policy": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "allowlist": _STRING_ARRAY_SCHEMA,
                        "denylist": _STRING_ARRAY_SCHEMA,
                    },
                },
                "api_checks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
                "markdown_report_example": {"type": "string"},
            },
        },
        "action_plan": {
            "type": "object",
            "additionalProperties": True,
            "required": ["immediate", "estimated_turns"],
            "properties": {
                "immediate": _STRING_ARRAY_SCHEMA,
                "sequential_dependencies": {"type": "string"},
                "estimated_turns": {"type": "string"},
            },
        },
    },
}
