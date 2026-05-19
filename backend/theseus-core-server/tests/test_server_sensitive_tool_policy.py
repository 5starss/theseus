import unittest

from src.config import Settings
from theseus_engine.models.rbac import (
    TheseusPermissionChecker,
    TheseusPermissionSettings,
)


class ServerSensitiveToolPolicyTest(unittest.TestCase):
    def test_settings_default_rejects_sensitive_tool_auto_allow(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual("reject", settings.THESEUS_SERVER_SENSITIVE_TOOL_POLICY)

    def test_settings_accepts_explicit_allow_policy(self) -> None:
        settings = Settings(
            _env_file=None,
            THESEUS_SERVER_SENSITIVE_TOOL_POLICY="allow",
        )

        self.assertEqual("allow", settings.THESEUS_SERVER_SENSITIVE_TOOL_POLICY)

    def test_sensitive_tool_auto_allow_depends_on_human_confirm_flag(self) -> None:
        blocked_checker = TheseusPermissionChecker(
            TheseusPermissionSettings(),
            user_level=3,
            tool_permissions={"bash": 3},
            require_human_confirm=True,
        )
        blocked = blocked_checker.evaluate(
            "bash",
            is_read_only=False,
            command="date",
        )

        allowed_checker = TheseusPermissionChecker(
            TheseusPermissionSettings(),
            user_level=3,
            tool_permissions={"bash": 3},
            require_human_confirm=False,
        )
        allowed = allowed_checker.evaluate(
            "bash",
            is_read_only=False,
            command="date",
        )

        self.assertFalse(blocked.allowed)
        self.assertTrue(blocked.requires_confirmation)
        self.assertTrue(allowed.allowed)
        self.assertFalse(allowed.requires_confirmation)


if __name__ == "__main__":
    unittest.main()
