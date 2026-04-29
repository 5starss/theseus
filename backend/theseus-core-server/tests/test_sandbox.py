import unittest
import asyncio
from src.sandbox.docker_executor import DockerExecutor
from src.sandbox.base import SandboxInput, SandboxUnavailableError

class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.executor = DockerExecutor()

    def test_basic_execution(self):
        code = """
def main(payload):
    return {"sum": payload["a"] + payload["b"]}
"""
        request = SandboxInput(
            project_id="test",
            tool_name="add",
            tool_code=code,
            payload={"a": 10, "b": 20},
            timeout_seconds=5
        )
        
        loop = asyncio.get_event_loop()
        output = loop.run_until_complete(self.executor.execute(request))
        self.assertTrue(output.success)
        self.assertEqual(output.result["sum"], 30)

    def test_timeout_execution(self):
        code = """
import time
def main(payload):
    time.sleep(10)
    return {"done": True}
"""
        request = SandboxInput(
            project_id="test",
            tool_name="slow",
            tool_code=code,
            payload={},
            timeout_seconds=2
        )
        
        loop = asyncio.get_event_loop()
        output = loop.run_until_complete(self.executor.execute(request))
        self.assertFalse(output.success)
        self.assertTrue(output.timed_out)
        self.assertEqual(output.error_message, "Execution timeout")

    def test_network_isolation(self):
        code = """
import urllib.request
def main(payload):
    urllib.request.urlopen("http://google.com", timeout=2)
    return {"connected": True}
"""
        request = SandboxInput(
            project_id="test",
            tool_name="net",
            tool_code=code,
            payload={},
            timeout_seconds=5
        )
        
        loop = asyncio.get_event_loop()
        output = loop.run_until_complete(self.executor.execute(request))
        self.assertFalse(output.success)
        error_info = output.stderr or str(output.error_message) or ""
        self.assertTrue(
            any(msg in error_info for msg in ["URLError", "Temporary failure", "name resolution", "Network is unreachable"]),
            f"Expected network error, but got: {error_info}"
        )

if __name__ == "__main__":
    unittest.main()
