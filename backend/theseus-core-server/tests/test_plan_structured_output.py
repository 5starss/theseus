from __future__ import annotations

import unittest

from src.tool_plan.planner import ToolPlanPlanner
from src.tool_plan.structured_output_schema import (
    plan_draft_json_schema,
    plan_draft_response_format,
    plan_draft_vllm_extra_body,
)
from theseus_engine.wrappers.llm_clients.api_types import ApiMessageRequest
from theseus_engine.wrappers.llm_clients.openai_compat_client import (
    _apply_openai_request_options,
)


class PlanStructuredOutputTest(unittest.TestCase):
    def test_schema_keeps_current_plan_shape(self) -> None:
        schema = plan_draft_json_schema()
        properties = schema["properties"]

        for key in (
            "goal",
            "context",
            "alternatives",
            "tasks",
            "verification",
            "execution_spec",
            "action_plan",
        ):
            self.assertIn(key, properties)

        task_properties = properties["tasks"]["items"]["properties"]
        for key in (
            "id",
            "parent_id",
            "tier",
            "title",
            "problem",
            "solution",
            "target_files",
            "expected_effect",
            "description",
            "status",
        ):
            self.assertIn(key, task_properties)

        execution_spec = properties["execution_spec"]["properties"]
        self.assertIn("permissionLevel", execution_spec)
        self.assertIn("permission_rationale", execution_spec)
        self.assertIn("validation_strategy", execution_spec)

    def test_response_format_and_vllm_extra_body_use_same_schema(self) -> None:
        response_format = plan_draft_response_format()
        extra_body = plan_draft_vllm_extra_body()

        self.assertEqual(response_format["type"], "json_schema")
        self.assertEqual(
            response_format["json_schema"]["schema"],
            extra_body["structured_outputs"]["json"],
        )

    def test_openai_request_options_apply_structured_output_params(self) -> None:
        response_format = plan_draft_response_format()
        extra_body = plan_draft_vllm_extra_body()
        request = ApiMessageRequest(
            model="vllm/test",
            messages=[],
            response_format=response_format,
            extra_body=extra_body,
        )
        params = {"model": "test", "messages": [], "stream": True}

        _apply_openai_request_options(params, request)

        self.assertIs(params["response_format"], response_format)
        self.assertIs(params["extra_body"], extra_body)

    def test_plan_payload_parser_accepts_raw_json(self) -> None:
        payload = ToolPlanPlanner._parse_plan_payload(
            '{"goal":"g","context":{},"tasks":[],"verification":{},"action_plan":{}}'
        )

        self.assertIsNotNone(payload)
        self.assertEqual(payload["goal"], "g")

    def test_plan_payload_parser_accepts_markdown_json_block(self) -> None:
        payload = ToolPlanPlanner._parse_plan_payload(
            'summary\n```json\n{"goal":"g","context":{},"tasks":[],"verification":{},"action_plan":{}}\n```'
        )

        self.assertIsNotNone(payload)
        self.assertEqual(payload["goal"], "g")


if __name__ == "__main__":
    unittest.main()
