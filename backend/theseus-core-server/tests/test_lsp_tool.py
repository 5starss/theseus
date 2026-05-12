import tempfile
import unittest
from pathlib import Path

from theseus_engine.tools.core.base_tools import ToolExecutionContext
from theseus_engine.tools.core.lsp_tool import LspInput, LspTool
import theseus_engine.tools.core.lsp_tool as lsp_module


class LspToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_lsp_rejects_paths_outside_workspace(self):
        original_jedi = lsp_module._jedi
        lsp_module._jedi = object()
        try:
            with tempfile.TemporaryDirectory() as workspace:
                with tempfile.TemporaryDirectory() as outside:
                    outside_file = Path(outside) / "outside.py"
                    outside_file.write_text("x = 1\n", encoding="utf-8")

                    result = await LspTool().execute(
                        LspInput(
                            operation="document_symbol",
                            file_path=str(outside_file),
                        ),
                        ToolExecutionContext(cwd=Path(workspace)),
                    )
        finally:
            lsp_module._jedi = original_jedi

        self.assertTrue(result.is_error)
        self.assertIn("outside the workspace root", result.output)


if __name__ == "__main__":
    unittest.main()
