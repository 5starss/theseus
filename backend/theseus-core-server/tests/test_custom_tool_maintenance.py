from __future__ import annotations

import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tool_plan import planner
from src.tooling.service import (
    STATUS_ACTIVE,
    ServerToolArtifactPaths,
    build_tool_paths,
    load_active_tools_for_project,
    read_project_tool_source,
    update_project_tool_source,
    write_tool_metadata,
)
from theseus_engine.tools.core.base_tools import ToolRegistry
from theseus_engine.tools.core.tool_factory import load_custom_tools_for_project as core_load_project_tools


def _tool_code(message: str = "ok") -> str:
    return textwrap.dedent(
        f"""
        from pydantic import BaseModel
        from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

        class RamMonitorInput(BaseModel):
            top_n: int = 10

        class RamMonitorTool(BaseTool):
            name = "ram_monitor"
            description = "RAM monitor."
            input_model = RamMonitorInput
            permission_level = 2

            async def execute(self, arguments: RamMonitorInput, context: ToolExecutionContext) -> ToolResult:
                return ToolResult(output="{message}")
        """
    ).strip() + "\n"


def _active_metadata(paths: ServerToolArtifactPaths) -> dict:
    return {
        "toolName": "ram_monitor",
        "moduleName": paths.module_name,
        "projectId": "4",
        "chatSessionId": 1,
        "creatorUserId": "7",
        "planId": "10",
        "fileName": paths.module_path.name,
        "createdAt": "2026-05-18T00:00:00+00:00",
        "updatedAt": "2026-05-18T00:00:00+00:00",
        "permissionLevel": 2,
        "status": STATUS_ACTIVE,
        "isActive": True,
        "validationResult": {
            "success": True,
            "status": "validated",
            "message": "ok",
            "checkedAt": "2026-05-18T00:00:00+00:00",
        },
        "sandboxResult": {
            "success": True,
            "status": "passed",
            "checkedAt": "2026-05-18T00:00:00+00:00",
        },
        "sandboxVerified": True,
        "activationSource": "server_toolbuild",
    }


def _write_active_tool(root: Path) -> ServerToolArtifactPaths:
    paths = build_tool_paths("4", "ram_monitor", storage_root=root)
    paths.project_dir.mkdir(parents=True, exist_ok=True)
    paths.module_path.write_text(_tool_code("old"), encoding="utf-8")
    write_tool_metadata(paths, _active_metadata(paths))
    return paths


class CustomToolMaintenanceTest(unittest.IsolatedAsyncioTestCase):
    def test_plan_custom_tool_paths_use_configured_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            configured = str((Path(tmp) / "custom_tools" / "projects").resolve())
            with patch.object(planner.settings, "THESEUS_PROJECT_CUSTOM_TOOLS_DIR", configured):
                root = planner._project_custom_tool_artifact_root(4)
                normalized = planner._normalize_project_custom_tool_path(
                    "theseus_engine/custom_tools/cpu_monitor_tool.py",
                    4,
                )
                normalized_project = planner._normalize_project_custom_tool_path(
                    "theseus_engine/custom_tools/projects/4/cpu_monitor_tool.meta.json",
                    4,
                )

            expected_root = str((Path(configured) / "4").resolve()).replace("\\", "/")
            self.assertEqual(expected_root, root)
            self.assertEqual(f"{expected_root}/cpu_monitor_tool.py", normalized)
            self.assertEqual(f"{expected_root}/cpu_monitor_tool.meta.json", normalized_project)

    async def test_read_and_update_active_tool_source_after_sandbox_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_active_tool(root)

            read_result = read_project_tool_source(
                project_id="4",
                tool_name="ram_monitor",
                storage_root=root,
            )
            self.assertEqual("read", read_result.status)
            self.assertIn("old", read_result.source or "")
            self.assertTrue(read_result.sandbox_verified)

            async def _sandbox_success(**_kwargs):
                return {
                    "success": True,
                    "status": "passed",
                    "error": "",
                    "logs": "",
                    "metadata": {},
                }

            with patch("src.tooling.service._run_tool_sandbox_gate", side_effect=_sandbox_success):
                update_result = await update_project_tool_source(
                    project_id="4",
                    tool_name="ram_monitor",
                    python_code=_tool_code("new"),
                    actor_user_id="7",
                    chat_session_id=1,
                    plan_id="10",
                    storage_root=root,
                    registry=ToolRegistry(),
                    active_registry=ToolRegistry(),
                    tool_permissions={},
                )

            self.assertEqual("updated", update_result.status)
            self.assertTrue(update_result.sandbox_verified)
            self.assertIn("new", paths.module_path.read_text(encoding="utf-8"))
            metadata = json.loads(paths.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual("custom_tool_update_source", metadata["activationSource"])
            self.assertTrue(metadata["sandboxVerified"])
            self.assertTrue(metadata["sandboxResult"]["success"])
            self.assertEqual([], list((paths.project_dir / ".staging").glob("*/*.py")))
            self.assertEqual([], list((paths.project_dir / ".staging").glob("*/*.meta.json")))

    async def test_sandbox_failure_preserves_existing_active_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _write_active_tool(root)
            old_source = paths.module_path.read_text(encoding="utf-8")

            async def _sandbox_failure(**_kwargs):
                return {
                    "success": False,
                    "status": "failed",
                    "error": "Permission denied",
                    "logs": "",
                    "metadata": {},
                    "errorType": "sandbox_unavailable",
                }

            with patch("src.tooling.service._run_tool_sandbox_gate", side_effect=_sandbox_failure):
                result = await update_project_tool_source(
                    project_id="4",
                    tool_name="ram_monitor",
                    python_code=_tool_code("new"),
                    actor_user_id="7",
                    chat_session_id=1,
                    plan_id="10",
                    storage_root=root,
                )

            self.assertEqual("rejected", result.status)
            self.assertEqual("sandbox_failed", result.stage)
            self.assertEqual(old_source, paths.module_path.read_text(encoding="utf-8"))
            metadata = json.loads(paths.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(STATUS_ACTIVE, metadata["status"])
            self.assertTrue(metadata["sandboxResult"]["success"])

    def test_project_loaders_skip_unverified_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = build_tool_paths("4", "ram_monitor", storage_root=root)
            paths.project_dir.mkdir(parents=True, exist_ok=True)
            paths.module_path.write_text(_tool_code("old"), encoding="utf-8")
            metadata = _active_metadata(paths)
            metadata["sandboxResult"] = {"success": False, "status": "failed"}
            write_tool_metadata(paths, metadata)

            server_registry = ToolRegistry()
            server_loaded = load_active_tools_for_project(
                server_registry,
                project_id="4",
                storage_root=root,
            )
            self.assertEqual([], server_loaded)

            core_registry = ToolRegistry()
            with patch.dict(os.environ, {"THESEUS_PROJECT_CUSTOM_TOOLS_DIR": str(root)}):
                core_loaded = core_load_project_tools(core_registry, "4")
            self.assertEqual([], core_loaded)


if __name__ == "__main__":
    unittest.main()
