import builtins
import unittest
from unittest.mock import patch

from src.auth.schemas import SessionContext
from src.builder.engine import EngineInitializationError, get_query_engine


class EngineAssemblyTests(unittest.TestCase):
    def test_get_query_engine_raises_controlled_error_when_openharness_missing(self):
        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("openharness"):
                raise ModuleNotFoundError(name)
            return original_import(name, globals, locals, fromlist, level)

        session = SessionContext(
            user_id=9999,
            project_id=8888,
            permission_level=1,
            token="test-token",
        )

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(EngineInitializationError) as exc_info:
                get_query_engine(session)

        self.assertIn("OpenHarness is not available", str(exc_info.exception))


if __name__ == "__main__":
    unittest.main()
