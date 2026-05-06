"""Theseus Meta-Tooling: Custom tool creation, validation, and dynamic loading module.

This module provides three core capabilities:
1. ToolValidator: Syntax and OpenHarness specification compliance validation
2. load_custom_tools: Auto-scan and register tools from the custom_tools/ directory
3. ToolCreatorTool: LLM-callable meta-tool to create new tools and inject them into the registry
"""

import os
import ast
import logging
import inspect
import importlib.util
from typing import Any, Dict, Tuple, Type, Optional, List, Set

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult, ToolRegistry

log = logging.getLogger(__name__)

# Directory where generated custom tools are stored
# 구조: backend/theseus-core-server/theseus_engine/tools/core/tool_factory.py
# 타겟: backend/theseus-core-server/theseus_engine/custom_tools/
CUSTOM_TOOLS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "custom_tools")
)

# Default permission level for tools without explicit permission_level
DEFAULT_PERMISSION_LEVEL = 1


class ToolValidator:
    """새로 생성된 툴 코드가 OpenHarness 규격에 맞는지 검증하는 유틸리티.

    검증 항목:
    - 파이썬 문법(Syntax) 검사
    - BaseTool / BaseModel 참조 존재 여부
    - execute 메소드 시그니처: (self, arguments, context) 3개 인자
    - ToolResult 올바른 사용법: output/is_error 키워드만 허용
    - context.input_model 안티패턴 감지
    - 보안 위반 검사: AnalysisValidator 위임 (AST 정적 분석)
    """

    @classmethod
    def validate_code(cls, code: str) -> Tuple[bool, str]:
        """파이썬 코드의 문법과 OpenHarness 구조 규칙을 AST로 검사합니다."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax Error: {e}"

        if "BaseTool" not in code or "BaseModel" not in code:
            return False, (
                "Code must import and use both BaseTool and BaseModel. "
                "Neither was found in the provided code."
            )

        # AST에서 BaseTool 상속 클래스 탐색
        errors: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # BaseTool을 상속하는 클래스인지 확인
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)
            if "BaseTool" not in base_names:
                continue

            # execute 메소드 시그니처 검증
            cls._check_execute_signature(node, errors)

        # ToolResult 잘못된 사용 패턴 탐지
        cls._check_tool_result_usage(tree, errors)

        # context.input_model 안티패턴 탐지
        cls._check_context_input_model(tree, errors)

        # 입력 모델 클래스명 화이트리스트 검증
        cls._check_input_model_naming(tree, errors)

        # 보안 위반 검사: AnalysisValidator에 위임
        from theseus_engine.validators.analysis_validator import (
            AnalysisValidator,
        )
        security_ok, security_msg = AnalysisValidator.validate(code)
        if not security_ok:
            errors.append(security_msg)

        if errors:
            return False, (
                "OpenHarness specification violations detected:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        return True, "Code syntax and structure validation passed."

    @classmethod
    def _check_execute_signature(
        cls,
        class_node: ast.ClassDef,
        errors: List[str],
    ) -> None:
        """execute 메소드의 인자가 (self, arguments, context)인지 검증합니다."""
        for item in class_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name != "execute":
                continue

            args = item.args
            # posonlyargs + args 합산 (self 포함 3개여야 함)
            all_args = list(args.posonlyargs) + list(args.args)
            arg_names = [a.arg for a in all_args]

            if len(arg_names) != 3:
                errors.append(
                    f"'{class_node.name}.execute()' has {len(arg_names)} arguments. "
                    f"Required signature: execute(self, arguments: <InputModel>, "
                    f"context: ToolExecutionContext) — exactly 3 arguments required."
                )
                return

            if arg_names[0] != "self":
                errors.append(
                    f"'{class_node.name}.execute()' first argument must be "
                    f"'self'. (found: '{arg_names[0]}')"
                )
            if arg_names[1] not in ("arguments", "args", "params", "input"):
                errors.append(
                    f"'{class_node.name}.execute()' second argument should receive "
                    f"the parsed input model (recommended: 'arguments'). "
                    f"(found: '{arg_names[1]}')"
                )
            if arg_names[2] != "context":
                errors.append(
                    f"'{class_node.name}.execute()' third argument must be "
                    f"'context'. (found: '{arg_names[2]}')"
                )
            return

        errors.append(
            f"Class '{class_node.name}' is missing the required "
            f"'execute' method definition."
        )

    @classmethod
    def _check_tool_result_usage(
        cls,
        tree: ast.Module,
        errors: List[str],
    ) -> None:
        """ToolResult의 잘못된 사용 패턴을 감지합니다.

        감지 대상:
        - ToolResult.from_error(...)  → 존재하지 않는 클래스 메소드
        - ToolResult(status=..., data=..., message=...)
            → 올바른 키워드는 output, is_error, metadata 뿐
        """
        VALID_KEYWORDS = {"output", "is_error", "metadata"}

        for node in ast.walk(tree):
            # ToolResult.from_error(...) 패턴 감지
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "ToolResult"
                    and func.attr == "from_error"
                ):
                    errors.append(
                        "ToolResult.from_error() does not exist. "
                        "Use ToolResult(output=..., is_error=True) instead."
                    )

                # ToolResult(...) 호출 시 키워드 검사
                if isinstance(func, ast.Name) and func.id == "ToolResult":
                    invalid_kws = [
                        kw.arg
                        for kw in node.keywords
                        if kw.arg is not None
                        and kw.arg not in VALID_KEYWORDS
                    ]
                    if invalid_kws:
                        errors.append(
                            f"ToolResult() received invalid keyword "
                            f"arguments: {', '.join(invalid_kws)}. "
                            f"Allowed keywords: {', '.join(sorted(VALID_KEYWORDS))}"
                        )

    @classmethod
    def _check_context_input_model(
        cls,
        tree: ast.Module,
        errors: List[str],
    ) -> None:
        """context.input_model 안티패턴을 감지합니다.

        OpenHarness에서 입력 데이터는 execute의 arguments 인자로
        전달되며, context.input_model은 존재하지 않습니다.
        """
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "input_model"
                and isinstance(node.value, ast.Name)
                and node.value.id == "context"
            ):
                errors.append(
                    "context.input_model does not exist. "
                    "Input data is passed as the 'arguments' parameter in "
                    "execute(self, arguments, context)."
                )
                break  # 한 번만 보고

    @classmethod
    def _check_input_model_naming(
        cls,
        tree: ast.Module,
        errors: List[str],
    ) -> None:
        """입력 모델 클래스명이 <ToolClassName>Input 패턴을 따르는지 검증합니다.

        Pydantic 스키마 캐시 충돌을 방지하기 위해 화이트리스트 방식으로
        모델명을 강제합니다.
        """
        tool_class_name = None
        input_model_names: List[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = [
                b.id for b in node.bases
                if isinstance(b, ast.Name)
            ]
            if "BaseTool" in base_names:
                tool_class_name = node.name
            elif "BaseModel" in base_names:
                input_model_names.append(node.name)

        if tool_class_name and input_model_names:
            expected = f"{tool_class_name}Input"
            for name in input_model_names:
                if name != expected:
                    errors.append(
                        f"To prevent Pydantic schema cache collisions, "
                        f"the input model for '{tool_class_name}' must be "
                        f"named '{expected}'. (found: '{name}')"
                    )

    # _check_security_violations: AnalysisValidator로 완전 이관됨.

    # ------------------------------------------------------------------
    # 2단계: 모듈 로드 및 런타임 규격 검증
    # ------------------------------------------------------------------

    @classmethod
    def validate_and_load_module(
        cls, module_name: str, file_path: str
    ) -> Tuple[bool, str, Optional[Type[BaseTool]]]:
        """모듈을 동적으로 로드하고 BaseTool 규격을 완벽히 준수하는지 검증합니다."""
        if not os.path.exists(file_path):
            return False, "File does not exist.", None

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return False, "Failed to load module spec.", None

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            return False, f"Error during module execution: {e}", None

        # BaseTool을 상속받은 클래스 탐색
        tool_classes = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseTool) and obj is not BaseTool:
                tool_classes.append(obj)

        if not tool_classes:
            return False, "No class inheriting from BaseTool was found.", None

        tool_class = tool_classes[0]  # 첫 번째 발견된 툴 클래스 사용

        # OpenHarness 필수 속성(name, description, input_model) 검증
        if not hasattr(tool_class, "name") or not getattr(tool_class, "name"):
            return False, "Tool class is missing the 'name' attribute or it is empty.", None
        if not hasattr(tool_class, "description") or not getattr(tool_class, "description"):
            return False, "Tool class is missing the 'description' attribute or it is empty.", None
        if not hasattr(tool_class, "input_model") or not issubclass(
            tool_class.input_model, BaseModel
        ):
            return (
                False,
                "Tool class is missing 'input_model' or it is not a subclass of BaseModel.",
                None,
            )

        # execute 메소드 런타임 시그니처 검증
        execute_method = getattr(tool_class, "execute", None)
        if execute_method is None:
            return False, "The 'execute' method is not defined.", None

        sig = inspect.signature(execute_method)
        params = list(sig.parameters.keys())
        # 바운드 메소드면 self 제외, 언바운드면 self 포함
        if params and params[0] == "self":
            params = params[1:]
        if len(params) != 2:
            return (
                False,
                f"execute method has incorrect signature. "
                f"({len(params)} args excluding self). "
                f"Required: execute(self, arguments, context)",
                None,
            )

        return True, f"Validation passed: tool '{tool_class.name}' loaded successfully.", tool_class


# ---------------------------------------------------------------------------
# Dynamic Tool Loader
# ---------------------------------------------------------------------------


def load_custom_tools(
    registry: ToolRegistry,
    tool_permissions: Optional[Dict[str, int]] = None,
    project_id: str | None = None,
) -> List[str]:
    """custom_tools/ 폴더 내의 모든 .py 파일을 스캔하여 ToolRegistry에 자동 등록합니다.

    각 툴 클래스에 `permission_level` 클래스 속성이 있으면 이를 읽어
    tool_permissions 딕셔너리에 자동으로 추가합니다.

    Args:
        registry: 툴을 등록할 ToolRegistry 인스턴스.
        tool_permissions: RBAC 권한 맵핑 딕셔너리. 이 함수가 로드한
            툴의 permission_level을 여기에 자동 추가합니다.

    Returns:
        성공적으로 로드된 툴 이름 목록.
    """
    if project_id:
        from src.tooling import load_custom_tools_for_project

        return load_custom_tools_for_project(
            registry,
            project_id=project_id,
            tool_permissions=tool_permissions,
        )

    loaded: List[str] = []

    if not os.path.isdir(CUSTOM_TOOLS_DIR):
        os.makedirs(CUSTOM_TOOLS_DIR, exist_ok=True)
        return loaded

    for filename in sorted(os.listdir(CUSTOM_TOOLS_DIR)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        module_name = filename[:-3]  # .py 제거
        file_path = os.path.join(CUSTOM_TOOLS_DIR, filename)

        is_valid, msg, tool_class = ToolValidator.validate_and_load_module(
            module_name, file_path
        )
        if is_valid and tool_class is not None:
            try:
                instance = tool_class()
                registry.register(instance)
                loaded.append(tool_class.name)

                # 툴의 permission_level을 RBAC 맵에 자동 등록
                level = getattr(
                    tool_class, "permission_level", DEFAULT_PERMISSION_LEVEL
                )
                if tool_permissions is not None:
                    tool_permissions[tool_class.name] = level
                    log.info(
                        "Custom tool loaded: %s (level=%d, file=%s)",
                        tool_class.name, level, filename,
                    )
            except Exception as e:
                log.warning("Failed to instantiate tool from %s: %s", filename, e)
        else:
            log.warning("Skipped invalid custom tool %s: %s", filename, msg)

    return loaded


def build_filtered_registry(
    full_registry: ToolRegistry,
    tool_permissions: Dict[str, int],
    user_level: int,
    exclude_tools: Optional[Set[str]] = None,
) -> ToolRegistry:
    """사용자의 권한 레벨에 따라 접근 가능한 툴만 담은 새 ToolRegistry를 생성합니다.

    LLM에게 이 필터링된 레지스트리를 전달하면, 권한 밖의 툴은
    API 스키마에 아예 포함되지 않아 에이전트가 존재 자체를 알 수 없게 됩니다.

    Args:
        full_registry: 모든 툴이 등록된 원본 ToolRegistry.
        tool_permissions: {tool_name: required_level} 맵핑.
        user_level: 현재 사용자의 권한 레벨 (자연수).
        exclude_tools: 이번 턴에서 제외할 툴 이름 집합 (모드별 필터링용).

    Returns:
        필터링된 ToolRegistry 인스턴스.
    """
    filtered = ToolRegistry()
    excluded = exclude_tools or set()
    for tool in full_registry.list_tools():
        if tool.name in excluded:
            continue
        required = tool_permissions.get(
            tool.name, DEFAULT_PERMISSION_LEVEL
        )
        if user_level >= required:
            filtered.register(tool)
    return filtered


# ---------------------------------------------------------------------------
# Meta-tool: create_tool
# ---------------------------------------------------------------------------


class ToolCreatorInput(BaseModel):
    """Input model for the create_tool meta-tool."""

    tool_name: str = Field(
        description="File name for the new tool (e.g. weather_fetcher)."
    )
    python_code: str = Field(
        description=(
            "A complete, self-contained Python module string that imports "
            "BaseTool and BaseModel and follows the OpenHarness tool specification. "
            "The BaseTool subclass MUST include a 'permission_level' class attribute. "
            "STRONGLY RECOMMENDED: Also include an 'example_queries' class attribute "
            "(list of 3-5 short user utterances in Korean and English) that would "
            "trigger this tool. This boosts retrieval accuracy in the RAG-based "
            "tool selector. Example: "
            "example_queries = ['날씨 알려줘', '오늘 비 와?', \"what's the weather\"]"
        )
    )
    permission_level: int = Field(
        default=1,
        description=(
            "Minimum permission level required to use this tool (positive integer). "
            "1 = anyone can use; higher values require higher privileges."
        ),
    )


ToolCreatorInput.model_rebuild()


class ToolCreatorTool(BaseTool):
    """새로운 Python 툴을 생성·검증·저장하고 즉시 사용 가능하게 등록합니다."""

    name = "create_tool"
    description = (
        "Create a new Python tool, validate its syntax and Theseus/OpenHarness "
        "compliance, and save it to the custom_tools directory. On success, "
        "the tool is registered in the current session's ToolRegistry and "
        "available from the NEXT turn. "
        "WHEN TO USE: Only use this tool when (1) you are in Plan mode's "
        "Executing phase, (2) the user's approved plan explicitly requires "
        "a new capability, and (3) no existing tool can accomplish the task. "
        "HOW TO USE: Produce a complete, self-contained, Pythonic module. "
        "Always declare an 'example_queries' class attribute listing 3-5 short "
        "user utterances (mix Korean/English) that should trigger this tool — "
        "this dramatically improves the RAG retriever's ability to surface it. "
        "CRITICAL: You CANNOT create a tool and call it in the SAME turn. "
        "You must call create_tool, wait for the success result, and ONLY "
        "THEN call the newly created tool in your next response."
    )
    input_model = ToolCreatorInput

    async def execute(
        self, arguments: ToolCreatorInput, context: ToolExecutionContext
    ) -> ToolResult:
        """툴 생성을 서버 래퍼 또는 레거시 경로로 위임합니다."""
        project_id = context.metadata.get("project_id")
        user_id = context.metadata.get("user_id")
        chat_session_id = context.metadata.get("chat_session_id")
        plan_id = context.metadata.get("plan_id")

        if project_id and user_id and chat_session_id is not None and plan_id:
            from src.tooling import ServerToolCreationRequest, create_tool_for_server

            result = await create_tool_for_server(
                ServerToolCreationRequest(
                    tool_name=arguments.tool_name,
                    python_code=arguments.python_code,
                    permission_level=arguments.permission_level,
                    project_id=str(project_id),
                    creator_user_id=str(user_id),
                    chat_session_id=int(chat_session_id),
                    plan_id=str(plan_id),
                ),
                registry=context.metadata.get("tool_registry"),
                tool_permissions=context.metadata.get("tool_permissions"),
            )
            return ToolResult(
                output=result.message,
                is_error=result.status != "created",
                metadata=result.to_metadata(),
            )

        return await self._execute_legacy(arguments, context)

    async def _execute_legacy(
        self, arguments: ToolCreatorInput, context: ToolExecutionContext
    ) -> ToolResult:
        from src.tooling.service import inject_permission_level

        os.makedirs(CUSTOM_TOOLS_DIR, exist_ok=True)
        file_path = os.path.join(CUSTOM_TOOLS_DIR, f"{arguments.tool_name}.py")

        try:
            code = inject_permission_level(
                arguments.python_code,
                arguments.permission_level,
            )
        except Exception as exc:
            return ToolResult(output=str(exc), is_error=True)

        is_valid_code, code_msg = ToolValidator.validate_code(code)
        if not is_valid_code:
            return ToolResult(
                output=f"❌ Code syntax/structure validation failed:\n{code_msg}",
                is_error=True,
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        is_valid_module, mod_msg, tool_class = ToolValidator.validate_and_load_module(
            arguments.tool_name, file_path
        )
        if not is_valid_module:
            os.remove(file_path)
            return ToolResult(
                output=f"❌ Tool specification validation failed (file rolled back):\n{mod_msg}",
                is_error=True,
            )

        registry = context.metadata.get("tool_registry")
        tool_permissions = context.metadata.get("tool_permissions")
        level = getattr(tool_class, "permission_level", arguments.permission_level)

        if registry is not None and tool_class is not None:
            try:
                registry.register(tool_class())
                if tool_permissions is not None:
                    tool_permissions[tool_class.name] = level
            except Exception as exc:
                return ToolResult(
                    output=(
                        f"✅ Tool file saved, but runtime registration failed: {exc}\n"
                        f"File: {file_path}\n"
                        f"The tool will be auto-loaded on the next session start."
                    )
                )

        return ToolResult(
            output=(
                f"✅ Tool '{tool_class.name}' created and validated!\n"
                f"File: {file_path}\n"
                f"Permission level: {level}\n"
                f"⚠️ Legacy mode created the tool outside the server wrapper."
            )
        )
