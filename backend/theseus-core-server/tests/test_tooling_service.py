import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tooling.service import (
    STATUS_ACTIVE,
    STATUS_SANDBOX_FAILED,
    STATUS_VALIDATED,
    ServerToolCreationRequest,
    create_tool_for_server,
    load_active_tools_for_project,
)


class FakeRegistry:
    def __init__(self):
        self.items = []

    def register(self, tool):
        self.items.append(tool)


class FakeSession:
    def close(self):
        return None


class AsyncToolingServiceTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_create_tool_for_server_activates_after_validation_and_sandbox(self):
        registry = FakeRegistry()
        permissions = {}

        class FakeTool:
            name = "weather_fetcher"
            description = "desc"
            input_model = object
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
                        with patch(
                            "src.tooling.service._run_tool_sandbox_gate",
                            return_value={
                                "success": True,
                                "status": "passed",
                                "logs": "ok",
                                "error": None,
                                "checkedAt": "2026-05-06T00:00:00+00:00",
                                "executionTimeMs": 10,
                                "exitCode": 0,
                                "timedOut": False,
                            },
                        ):
                            result = await create_tool_for_server(
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

            metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], STATUS_ACTIVE)
            self.assertTrue(metadata["isActive"])
            self.assertEqual(metadata["validationResult"]["status"], STATUS_VALIDATED)
            self.assertTrue(metadata["validationResult"]["success"])
            self.assertTrue(metadata["sandboxResult"]["success"])
            self.assertEqual(metadata["sandboxResult"]["status"], "passed")

    async def test_create_tool_for_server_persists_but_does_not_activate_when_sandbox_fails(self):
        registry = FakeRegistry()
        permissions = {}

        class FakeTool:
            name = "weather_fetcher"
            description = "desc"
            input_model = object
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
                        with patch(
                            "src.tooling.service._run_tool_sandbox_gate",
                            return_value={
                                "success": False,
                                "status": "failed",
                                "logs": "boom",
                                "error": "sandbox import failed",
                                "checkedAt": "2026-05-06T00:00:00+00:00",
                                "executionTimeMs": 10,
                                "exitCode": 1,
                                "timedOut": False,
                            },
                        ):
                            result = await create_tool_for_server(
                                self.request,
                                registry=registry,
                                tool_permissions=permissions,
                                storage_root=Path(tmpdir),
                            )

            self.assertEqual(result.status, "rejected")
            self.assertEqual(result.stage, "sandbox_failed")
            self.assertEqual(len(registry.items), 0)
            self.assertEqual(permissions, {})
            self.assertTrue(Path(result.module_path).exists())
            self.assertTrue(Path(result.metadata_path).exists())

            metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], STATUS_SANDBOX_FAILED)
            self.assertFalse(metadata["isActive"])
            self.assertTrue(metadata["validationResult"]["success"])
            self.assertFalse(metadata["sandboxResult"]["success"])
            self.assertEqual(metadata["sandboxResult"]["error"], "sandbox import failed")

    async def test_create_tool_for_server_rejects_invalid_plan_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.tooling.service._session_local_factory", return_value=lambda: FakeSession()):
                with patch(
                    "src.tooling.service._assert_plan_execution_context",
                    side_effect=RuntimeError("Plan is not in executing state"),
                ):
                    result = await create_tool_for_server(
                        self.request,
                        storage_root=Path(tmpdir),
                    )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.stage, "plan_guard")
        self.assertEqual(result.errors, ["Plan is not in executing state"])


class ToolingLoaderTests(unittest.TestCase):
    def test_load_active_tools_for_project_only_restores_active_metadata(self):
        registry = FakeRegistry()
        permissions = {}

        class ActiveTool:
            name = "tool_a"
            permission_level = 1

        class InactiveTool:
            name = "tool_b"
            permission_level = 3

        def fake_validate(module_name, _file_path):
            if module_name.startswith("project_a__tool_a"):
                return True, "ok", ActiveTool
            if module_name.startswith("project_a__tool_b"):
                return True, "ok", InactiveTool
            return False, "invalid", None

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_dir = root / "project_a"
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "tool_a.py").write_text("# a", encoding="utf-8")
            (project_dir / "tool_b.py").write_text("# b", encoding="utf-8")
            (project_dir / "tool_a.meta.json").write_text(
                json.dumps(
                    {
                        "status": STATUS_ACTIVE,
                        "isActive": True,
                        "validationResult": {"success": True},
                        "sandboxResult": {"success": True},
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "tool_b.meta.json").write_text(
                json.dumps(
                    {
                        "status": STATUS_SANDBOX_FAILED,
                        "isActive": False,
                        "validationResult": {"success": True},
                        "sandboxResult": {"success": False},
                    }
                ),
                encoding="utf-8",
            )

            with patch("src.tooling.service._tool_validator_cls") as validator_factory:
                validator_factory.return_value = type(
                    "Validator",
                    (),
                    {"validate_and_load_module": staticmethod(fake_validate)},
                )
                loaded = load_active_tools_for_project(
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
