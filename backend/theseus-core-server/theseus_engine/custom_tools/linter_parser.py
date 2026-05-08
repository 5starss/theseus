from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field
import json
import re

class LinterParserToolInput(BaseModel):
    raw_output: str = Field(..., description="The raw text output from flake8 or pylint.")
    linter_type: str = Field(..., description="The type of linter used ('flake8' or 'pylint').")

class LinterParserTool(BaseTool):
    name: str = "linter_parser"
    description: str = "Parses raw text output from flake8 or pylint into a structured JSON array."
    input_model: type[BaseModel] = LinterParserToolInput
    permission_level: int = 1

    async def execute(self, arguments: LinterParserToolInput, context: ToolExecutionContext) -> ToolResult:
        linter = arguments.linter_type.lower()
        raw_output = arguments.raw_output.strip()
        
        if not raw_output:
            return ToolResult(output="[]")

        if linter == "flake8":
            return self._parse_flake8(raw_output)
        elif linter == "pylint":
            return self._parse_pylint(raw_output)
        else:
            return ToolResult(output=f"Error: Unsupported linter '{linter}'.", is_error=True)

    def _parse_flake8(self, text: str) -> ToolResult:
        results = []
        for line in text.split('\n'):
            if not line: continue
            # flake8 format: path:line:col: code message
            # or with custom format: path:line:col:code:message
            match = re.match(r"([^:]+):(\d+):(\d+):(?:([^:]+):)?(.+)", line)
            if match:
                code = match.group(4) if match.group(4) and not match.group(4).isdigit() else match.group(3)
                # If the regex above is too complex, let's use a more robust one for standard flake8
                # Standard: file:line:col: CODE message
                # Let's try:
                standard_match = re.match(r"([^:]+):(\d+):(\d+): ([^ ]+) (.+)", line)
                if standard_match:
                    results.append({
                        "file": standard_match.group(1),
                        "line": int(standard_match.group(2)),
                        "column": int(standard_match.group(3)),
                        "code": standard_match.group(4),
                        "message": standard_match.group(5).strip()
                    })
                else:
                    # Try the other one
                    results.append({
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "column": int(match.group(3)),
                        "code": match.group(4) or "N/A",
                        "message": match.group(5).strip()
                    })
        return ToolResult(output=json.dumps(results))

    def _parse_pylint(self, text: str) -> ToolResult:
        if text.startswith('['):
            try:
                data = json.loads(text)
                results = []
                for issue in data:
                    results.append({
                        "file": issue.get("path"),
                        "line": issue.get("line"),
                        "column": issue.get("column"),
                        "code": issue.get("symbol") or issue.get("message"),
                        "message": issue.get("message")
                    })
                return ToolResult(output=json.dumps(results))
            except json.JSONDecodeError:
                pass

        results = []
        for line in text.split('\n'):
            if not line: continue
            match = re.match(r"([^:]+):(\d+):(\d+): (.+)", line)
            if match:
                results.append({
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                    "code": "N/A",
                    "message": match.group(4).strip()
                })
        return ToolResult(output=json.dumps(results))

    @classmethod
    def get_example_queries(cls) -> list[str]:
        return [
            "flake8 결과 파싱해줘",
            "pylint 로그를 JSON으로 변환해줘",
            "parse flake8 output"
        ]
