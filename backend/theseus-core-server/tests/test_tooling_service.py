import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tooling.service import (
    ServerToolCreationRequest,
    create_tool_for_server,
    load_custom_tools_for_project,
)


class FakeRegistry:
    def __init__(self):
        self.items = []

    def register(self, tool):
        self.items.append(tool)


class FakeSession:
    def close(self):
        return None


class ToolingServiceTests(unittest.TestCase):
    def setUp(self):
        self.request = ServerToolCreationRequest(
            tool_name="weather_fetcher",
            python_code="class Example:\n    name = 'weather_fetcher'\n",
            permission_level=2,
            project_id="proj-123",
            creator_user_id="user-1",
            chat_session_id=77,
            plan_id="plan-1",
        )

    def test_create_tool_for_server_persists_project_scoped_files_and_metadata(self):
        registry = FakeRegistry()
        permissions = {}

        class FakeTool:
            name = "weather_fetcher"
            permission_level = 2

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.tooling.service._session_local_factory", return_value=lambda: FakeSession()):
                with patch("src.tooling.service._assert_plan_execution_context"):
                    with patch("src.tooling.service._tool_validator_cls") as validator_factory:
                        validator_factory.return_value = type(
                            "Validator",
                            (),
                            {
                                "validate_code": staticmethod(lambda _code: (True, "ok")),
                                "validate_and_load_module": staticmethod(
                                    lambda _module_name, _file_path: (True, "ok", FakeTool)
                                ),
                            },
                        )
                        result = create_tool_for_server(
                            self.request,
                            registry=registry,
                            tool_permissions=permissions,
                            storage_root=Path(tmpdir),
                        )

            self.assertEqual(result.status, "created")
            self.assertEqual(result.stage, "completed")
            self.assertTrue(result.registry_registered)
            self.assertEqual(len(registry.items), 1)
            self.assertEqual(permissions["weather_fetcher"], 2)

            module_path = Path(result.module_path)
            metadata_path = Path(result.metadata_path)
            self.assertTrue(module_path.exists())
            self.assertTrue(metadata_path.exists())
            self.assertEqual(module_path.parent.name, "proj_123")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["projectId"], "proj-123")
            self.assertEqual(metadata["creatorUserId"], "user-1")
            self.assertEqual(metadata["chatSessionId"], 77)
            self.assertEqual(metadata["planId"], "plan-1")
            self.assertEqual(metadata["approvalHistory"][0]["status"], "approved_for_execution")

    def test_create_tool_for_server_standardizes_validator_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.tooling.service._session_local_factory", return_value=lambda: FakeSession()):
                with patch("src.tooling.service._assert_plan_execution_context"):
                    with patch("src.tooling.service._tool_validator_cls") as validator_factory:
                        validator_factory.return_value = type(
                            "Validator",
                            (),
                            {
                                "validate_code": staticmethod(
                                    lambda _code: (False, "Syntax Error: invalid syntax")
                                ),
                                "validate_and_load_module": staticmethod(
                                    lambda _module_name, _file_path: (False, "invalid", None)
                                ),
                            },
                        )
                        result = create_tool_for_server(
                            self.request,
                            storage_root=Path(tmpdir),
                        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.stage, "code_validation")
        self.assertIn("Syntax Error", result.message)
        self.assertEqual(result.errors, ["Syntax Error: invalid syntax"])

    def test_create_tool_for_server_rejects_invalid_plan_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.tooling.service._session_local_factory", return_value=lambda: FakeSession()):
                with patch(
                    "src.tooling.service._assert_plan_execution_context",
                    side_effect=RuntimeError("Plan is not in executing state"),
                ):
                    result = create_tool_for_server(
                        self.request,
                        storage_root=Path(tmpdir),
                    )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.stage, "plan_guard")
        self.assertEqual(result.errors, ["Plan is not in executing state"])

    def test_load_custom_tools_for_project_is_project_scoped(self):
        registry = FakeRegistry()
        permissions = {}

        class ProjectATool:
            name = "tool_a"
            permission_level = 1

        class ProjectBTool:
            name = "tool_b"
            permission_level = 3

        def fake_validate(module_name, file_path):
            if module_name.startswith("project_a__"):
                return True, "ok", ProjectATool
            if module_name.startswith("project_b__"):
                return True, "ok", ProjectBTool
            return False, "invalid", None

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_a = root / "project_a"
            project_b = root / "project_b"
            project_a.mkdir(parents=True, exist_ok=True)
            project_b.mkdir(parents=True, exist_ok=True)
            (project_a / "tool_a.py").write_text("# a", encoding="utf-8")
            (project_b / "tool_b.py").write_text("# b", encoding="utf-8")

            with patch("src.tooling.service._tool_validator_cls") as validator_factory:
                validator_factory.return_value = type(
                    "Validator",
                    (),
                    {
                        "validate_code": staticmethod(lambda _code: (True, "ok")),
                        "validate_and_load_module": staticmethod(fake_validate),
                    },
                )
                loaded = load_custom_tools_for_project(
                    registry,
                    project_id="project-a",
                    tool_permissions=permissions,
                    storage_root=root,
                )

        self.assertEqual(loaded, ["tool_a"])
        self.assertEqual([tool.name for tool in registry.items], ["tool_a"])
        self.assertEqual(permissions["tool_a"], 1)
        self.assertNotIn("tool_b", permissions)


if __name__ == "__main__":
    unittest.main()
