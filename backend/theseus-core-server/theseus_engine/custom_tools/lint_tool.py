import re
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Union
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

class LintToolInput(BaseModel):
    file_path: str = Field(..., description="분석할 파이썬 파일의 경로")
    linter_type: str = Field("flake8", description="사용할 linter 종류 ('flake8' 또는 'pylint')")

class LintTool(BaseTool):
    name: str = "lint_tool"
    description: str = "flake8 또는 pylint를 실행하여 파일의 에러/경고 내역을 JSON 배열로 반환합니다."
    input_model: type[BaseModel] = LintToolInput
    permission_level: int = 1

    async def execute(self, arguments: LintToolInput, context: ToolExecutionContext) -> ToolResult:
        file_path = Path(arguments.file_path).resolve()
        
        if not file_path.exists():
            return ToolResult(output=json.dumps([{"error": f"File not found: {file_path}"}]), is_error=True)

        if arguments.linter_type == "flake8":
            return await self._run_flake8(file_path, context)
        elif arguments.linter_type == "pylint":
            return await self._run_pylint(file_path, context)
        else:
            return ToolResult(output=json.dumps([{"error": f"Unsupported linter: {arguments.linter_type}"}]), is_error=True)

    async def _run_flake8(self, file_path: Path, context: ToolExecutionContext) -> ToolResult:
        # flake8 format: path:line:col: code message
        # Using context.run_shell to execute commands
        cmd = f'flake8 "{file_path}" --format="%(path)s:%(row)d:%(col)d:%(code)s:%(text)s"'
        
        try:
            result = await context.run_shell(cmd)
            output_text = result.stdout.strip()
            
            if not output_text:
                return ToolResult(output=json.dumps([]))

            issues = []
            # Pattern to match: path:line:col:code:message
            # Using a simpler regex since 'compile' was flagged, although 're' is allowed. 
            # Wait, 'compile' might refer to 're.compile'. Let's try without it if it keeps failing.
            # But actually, re.compile is often okay, let's see if I can use re.match directly.
            
            for line in output_text.splitlines():
                parts = line.split(':', 4)
                if len(parts) >= 5:
                    # parts[0] is path, [1] line, [2] col, [3] code, [4] message
                    issues.append({
                        "line": int(parts[1]),
                        "column": int(parts[2]),
                        "code": parts[3],
                        "message": parts[4].strip()
                    })
            
            return ToolResult(output=json.dumps(issues, ensure_ascii=False))
        except Exception as e:
            return ToolResult(output=json.dumps([{"error": str(e)}]), is_error=True)

    async def _run_pylint(self, file_path: Path, context: ToolExecutionContext) -> ToolResult:
        # Use pylint's built-in JSON output
        cmd = f'pylint "{file_path}" --output-format=json'
        
        try:
            result = await context.run_shell(cmd)
            output_text = result.stdout.strip()
            
            if not output_text:
                return ToolResult(output=json.dumps([]))

            raw_json = json.loads(output_text)
            issues = []
            for item in raw_json:
                issues.append({
                    "line": item.get("line", 0),
                    "column": item.get("column", 0),
                    "code": item.get("symbol", item.get("message-id", "")),
                    "message": item.get("message", "")
                })
            
            return ToolResult(output=json.dumps(issues, ensure_ascii=False))
        except json.JSONDecodeError:
            return ToolResult(output=json.dumps([{"error": "Failed to parse pylint JSON output"}]), is_error=True)
        except Exception as e:
            return ToolResult(output=json.dumps([{"error": str(e)}]), is_error=True)

    @classmethod
    def get_example_queries(cls) -> List[str]:
        return [
            "이 파일의 에러 좀 찾아줘 (flake8)",
            "pylint로 이 코드 검사해줘",
            "lint_tool 실행해서 결과 보여줘"
        ]
