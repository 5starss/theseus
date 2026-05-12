import unittest
from unittest.mock import patch

from theseus_engine.tasks.manager import TaskInfo, TheseusTaskManager


class FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def read(self, size: int) -> bytes:
        del size
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class FakeProcess:
    def __init__(self) -> None:
        self.stdout = FakeStdout([b"1234567890", b"abcdef"])
        self.returncode = 0

    async def wait(self) -> None:
        return None


class TaskManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_watch_caps_output_buffer(self):
        manager = TheseusTaskManager()
        task = TaskInfo(
            id="task1",
            type="shell",
            description="test",
            _process=FakeProcess(),
        )

        with patch("theseus_engine.tasks.manager.MAX_OUTPUT_BYTES", 10):
            await manager._watch(task)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task._output_buffer.decode("utf-8"), "7890abcdef")
        self.assertTrue(task.metadata["output_truncated"])


if __name__ == "__main__":
    unittest.main()
