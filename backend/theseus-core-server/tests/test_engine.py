import unittest

from src.auth.schemas import SessionContext
from src.builder.engine import get_query_engine


class EngineAssemblyTests(unittest.TestCase):
    def test_get_query_engine_uses_theseus_native_engine(self):
        session = SessionContext(
            user_id=9999,
            project_id=8888,
            permission_level=1,
            token="test-token",
        )

        assembly = get_query_engine(session)

        self.assertEqual(assembly.model_name, "gpt-4o")
        self.assertIn("dummy_echo", assembly.allowed_tools)


if __name__ == "__main__":
    unittest.main()
