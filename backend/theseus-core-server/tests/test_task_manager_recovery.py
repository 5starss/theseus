from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from theseus_engine.tasks.manager import TaskInfo, TheseusTaskManager


class TaskManagerRecoveryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.data_dir = self.root / "task-data"
        self.env_patch = patch.dict(
            os.environ,
            {"THESEUS_TASK_DATA_DIR": str(self.data_dir)},
        )
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.tempdir.cleanup()

    async def test_stop_recovers_persisted_task_pid_after_restart(self) -> None:
        manager = TheseusTaskManager()
        task = TaskInfo(
            id="abc123",
            type="shell",
            description="long running monitor",
            command="python monitor.py",
            cwd=str(self.workspace),
            pid=43210,
            log_path=str(self.data_dir / "monitor.log"),
        )
        manager._save_task_record(task)

        fresh_manager = TheseusTaskManager()
        with (
            patch("theseus_engine.tasks.manager._is_pid_running", return_value=True),
            patch(
                "theseus_engine.tasks.manager._terminate_process_tree",
                new=AsyncMock(return_value=True),
            ) as terminate_tree,
        ):
            stopped = await fresh_manager.stop_task("abc123", cwd=self.workspace)

        self.assertEqual(stopped.status, "stopped")
        terminate_tree.assert_awaited_once()
        self.assertEqual(terminate_tree.await_args.args[1], 43210)

    async def test_running_persisted_task_without_live_pid_becomes_exited(self) -> None:
        manager = TheseusTaskManager()
        task = TaskInfo(
            id="deadpid",
            type="shell",
            description="old monitor",
            command="python monitor.py",
            cwd=str(self.workspace),
            pid=54321,
        )
        manager._save_task_record(task)

        fresh_manager = TheseusTaskManager()
        with patch("theseus_engine.tasks.manager._is_pid_running", return_value=False):
            tasks = fresh_manager.list_tasks(cwd=self.workspace)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].status, "exited")

        record = json.loads(Path(tasks[0].record_path).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "exited")

    async def test_stop_refuses_reused_pid_identity(self) -> None:
        manager = TheseusTaskManager()
        task = TaskInfo(
            id="reused",
            type="shell",
            description="old monitor",
            command="python monitor.py",
            cwd=str(self.workspace),
            pid=65432,
            metadata={"process_identity": "old-process"},
        )
        manager._save_task_record(task)

        fresh_manager = TheseusTaskManager()
        with (
            patch("theseus_engine.tasks.manager._is_pid_running", return_value=True),
            patch(
                "theseus_engine.tasks.manager._process_identity",
                return_value="new-process",
            ),
            patch(
                "theseus_engine.tasks.manager._terminate_process_tree",
                new=AsyncMock(return_value=True),
            ) as terminate_tree,
        ):
            stopped = await fresh_manager.stop_task("reused", cwd=self.workspace)

        self.assertEqual(stopped.status, "exited")
        terminate_tree.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
