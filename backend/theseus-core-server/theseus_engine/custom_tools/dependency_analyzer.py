import ast
import os
from pathlib import Path
from typing import List, Set, Dict, Any
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class DependencyAnalyzerToolInput(BaseModel):
    directory_path: str = Field(..., description="분석할 대상 디렉토리의 절대 경로 또는 상대 경로")

class DependencyAnalyzerTool(BaseTool):
    name = "dependency_analyzer"
    description = "파이썬 파일의 AST를 분석하여 로컬 파일 간의 의존성 그래프를 생성합니다."
    input_model = DependencyAnalyzerToolInput
    permission_level = 1

    def _get_local_modules(self, root_dir: Path) -> Set[str]:
        """디렉토리 내의 모든 .py 파일로부터 모듈 이름을 수집합니다."""
        modules = set()
        for path in root_dir.rglob("*.py"):
            # 파일 경로를 모듈 경로로 변환 (예: sub/dir/file.py -> sub.dir.file)
            relative_path = path.relative_to(root_dir)
            module_parts = list(relative_path.with_suffix("").parts)
            module_name = ".".join(module_parts)
            modules.add(module_name)
            # __init__.py 인 경우 패키지 이름만 추가
            if path.name == "__init__.py":
                package_name = ".".join(module_parts[:-1])
                if package_name:
                    modules.add(package_name)
        return modules

    def _extract_imports(self, file_path: Path, root_dir: Path, local_modules: Set[str]) -> Set[str]:
        """파일의 AST를 분석하여 로컬 모듈에 대한 임포트 목록을 반환합니다."""
        imports = set()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in local_modules:
                        imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:  # Relative import
                    pass 
                elif node.module:
                    if node.module in local_modules:
                        imports.add(node.module)
        return imports

    async def execute(self, arguments: DependencyAnalyzerToolInput, context: ToolExecutionContext) -> ToolResult:
        root_path = Path(arguments.directory_path).resolve()
        
        if not root_path.exists() or not root_path.is_dir():
            return ToolResult(output=f"Error: {arguments.directory_path} is not a valid directory.", is_error=True)

        # 1. 모든 로컬 모듈 리스트 확보
        local_modules = self._get_local_modules(root_path)
        
        nodes = []
        edges = []

        # 2. 각 파일 탐색 및 의존성 추출
        for py_file in root_path.rglob("*.py"):
            # 현재 파일의 모듈 이름 계산
            rel_path = py_file.relative_to(root_path)
            module_name = ".".join(list(rel_path.with_suffix("").parts))
            if py_file.name == "__init__.py":
                module_name = ".".join(list(rel_path.with_suffix("").parts)[:-1])
                if not module_name: module_name = "" # root __init__

            if not module_name: continue

            nodes.append({"id": module_name, "file": str(py_file.relative_to(root_path))})

            found_imports = self._extract_imports(py_file, root_path, local_modules)
            for imp in found_imports:
                if imp != module_name: # 자기 자신 제외
                    edges.append({"source": module_name, "target": imp})

        result = {
            "nodes": nodes,
            "edges": edges
        }

        import json
        return ToolResult(output=json.dumps(result, indent=2))

    @classmethod
    def example_queries(cls) -> List[str]:
        return [
            "이 디렉토리의 파이썬 의존성을 분석해줘",
            "Analyze python dependencies in this folder",
            "파이썬 파일들 사이의 관계를 JSON으로 뽑아줘"
        ]
