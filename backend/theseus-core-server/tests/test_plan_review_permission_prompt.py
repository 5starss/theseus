from __future__ import annotations

import unittest

from theseus_engine.prompts.plan import PLAN_REVIEW_PROMPT


class PlanReviewPermissionPromptTest(unittest.TestCase):
    def test_review_prompt_mentions_execution_permission_fields(self) -> None:
        self.assertIn("execution_spec.permissionLevel", PLAN_REVIEW_PROMPT)
        self.assertIn("execution_spec.permission_rationale", PLAN_REVIEW_PROMPT)
        self.assertIn("change to 2", PLAN_REVIEW_PROMPT)


if __name__ == "__main__":
    unittest.main()
