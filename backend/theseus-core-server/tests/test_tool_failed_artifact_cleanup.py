from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tooling.service import (
    STATUS_ACTIVE,
    STATUS_SANDBOX_FAILED,
    ServerToolArtifactPaths,
    ServerToolCreationRequest,
    ToolCreationError,
    build_tool_paths,
    cleanup_failed_tool_artifact,
    persist_draft_tool,
    validate_draft_tool,
)


class _RejectingValidator:
    @staticmethod
    def validate_code(_code: str) -> tuple[bool, str]:
        return False, "No class inheriting from BaseTool was found."


def _request(tool_name: str, *, plan_id: str = "10") -> ServerToolCreationRequest:
    return ServerToolCreationRequest(
        tool_name=tool_name,
        python_code=(
            "class NotATheseusTool:\n"
            f"    name = '{tool_name}'\n"
            "    permission_level = 1\n"
        ),
        permission_level=1,
        project_id="1",
        creator_user_id="7",
        chat_session_id=99,
        plan_id=plan_id,
        run_id="run-1",
    )


class ToolFailedArtifactCleanupTest(unittest.TestCase):
    def test_validation_failed_artifact_is_deleted_after_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = _request("cleanup_validation_tool")
            paths, _metadata = persist_draft_tool(request, storage_root=root)

            with patch(
                "src.tooling.service._tool_validator_cls",
                return_value=_RejectingValidator,
            ):
                with self.assertRaises(ToolCreationError):
                    validate_draft_tool(paths)

            report = cleanup_failed_tool_artifact(
                paths,
                request=request,
                failure_stage="validation_failed",
                failure_code="VALIDATION_FAILED",
                failure_message="not a BaseTool subclass",
                storage_root=root,
            )

            self.assertTrue(report["cleanupAttempted"])
            self.assertTrue(report["cleanupSucceeded"])
            self.assertFalse(paths.module_path.exists())
            self.assertFalse(paths.metadata_path.exists())

            retry_paths, retry_metadata = persist_draft_tool(
                _request("cleanup_validation_tool", plan_id="11"),
                storage_root=root,
            )
            self.assertTrue(retry_paths.module_path.exists())
            self.assertTrue(retry_paths.metadata_path.exists())
            self.assertEqual("11", retry_metadata["planId"])

    def test_stale_inactive_artifact_is_cleaned_before_new_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale_paths = build_tool_paths("1", "stale_cleanup_tool", storage_root=root)
            stale_paths.project_dir.mkdir(parents=True, exist_ok=True)
            stale_paths.module_path.write_text("# stale failed artifact\n", encoding="utf-8")
            stale_paths.metadata_path.write_text(
                json.dumps(
                    {
                        "toolName": "stale_cleanup_tool",
                        "moduleName": stale_paths.module_name,
                        "projectId": "1",
                        "planId": "old-plan",
                        "status": STATUS_SANDBOX_FAILED,
                        "isActive": False,
                    }
                ),
                encoding="utf-8",
            )

            request = _request("stale_cleanup_tool", plan_id="new-plan")
            retry_paths, retry_metadata = persist_draft_tool(request, storage_root=root)

            self.assertEqual(stale_paths.module_path, retry_paths.module_path)
            self.assertEqual("new-plan", retry_metadata["planId"])
            self.assertTrue(retry_paths.module_path.exists())

    def test_active_artifact_is_never_deleted_by_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = build_tool_paths("1", "active_cleanup_tool", storage_root=root)
            paths.project_dir.mkdir(parents=True, exist_ok=True)
            paths.module_path.write_text("# active tool\n", encoding="utf-8")
            paths.metadata_path.write_text(
                json.dumps(
                    {
                        "toolName": "active_cleanup_tool",
                        "moduleName": paths.module_name,
                        "projectId": "1",
                        "planId": "10",
                        "status": STATUS_ACTIVE,
                        "isActive": True,
                    }
                ),
                encoding="utf-8",
            )

            report = cleanup_failed_tool_artifact(
                paths,
                request=None,
                failure_stage="sandbox_failed",
                failure_message="should not delete active tools",
                storage_root=root,
                require_request_match=False,
            )

            self.assertFalse(report["cleanupSucceeded"])
            self.assertEqual("active_artifact", report["skippedReason"])
            self.assertTrue(paths.module_path.exists())
            self.assertTrue(paths.metadata_path.exists())

    def test_metadata_missing_orphan_keeps_name_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = build_tool_paths("1", "orphan_cleanup_tool", storage_root=root)
            paths.project_dir.mkdir(parents=True, exist_ok=True)
            paths.module_path.write_text("# orphan\n", encoding="utf-8")

            with self.assertRaises(ToolCreationError) as raised:
                persist_draft_tool(_request("orphan_cleanup_tool"), storage_root=root)

            self.assertEqual("tool_name_conflict", raised.exception.stage)
            self.assertTrue(paths.module_path.exists())

    def test_outside_root_artifact_is_not_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            outside = Path(tmp) / "outside"
            outside.mkdir(parents=True)
            paths = ServerToolArtifactPaths(
                project_dir=outside,
                module_path=outside / "outside_tool.py",
                metadata_path=outside / "outside_tool.meta.json",
                module_name="outside_tool",
            )
            paths.module_path.write_text("# outside\n", encoding="utf-8")
            paths.metadata_path.write_text(
                json.dumps(
                    {
                        "toolName": "outside_tool",
                        "moduleName": "outside_tool",
                        "projectId": "1",
                        "planId": "10",
                        "status": STATUS_SANDBOX_FAILED,
                        "isActive": False,
                    }
                ),
                encoding="utf-8",
            )

            report = cleanup_failed_tool_artifact(
                paths,
                request=None,
                failure_stage="sandbox_failed",
                storage_root=root,
                require_request_match=False,
            )

            self.assertFalse(report["cleanupSucceeded"])
            self.assertEqual("outside_project_tool_root", report["skippedReason"])
            self.assertTrue(paths.module_path.exists())
            self.assertTrue(paths.metadata_path.exists())


if __name__ == "__main__":
    unittest.main()
