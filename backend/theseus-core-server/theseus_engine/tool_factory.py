"""Theseus 메타-툴링: 커스텀 툴 생성, 검증, 동적 로딩 모듈.

이 모듈은 세 가지 핵심 기능을 제공합니다:
1. ToolValidator: 생성된 코드의 문법 및 OpenHarness 규격 검증
2. load_custom_tools: custom_tools/ 폴더를 스캔하여 ToolRegistry에 자동 등록
3. ToolCreatorTool: LLM이 호출하여 새 툴을 생성하고, 즉시 레지스트리에 주입
"""

import os
import re
import ast
import logging
import inspect
import importlib.util
from typing import Any, Dict, Tuple, Type, Optional, List, Set

from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult, ToolRegistry

log = logging.getLogger(__name__)

# 생성된 커스텀 툴들이 저장될 디렉토리
CUSTOM_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "custom_tools")

# 툴의 기본 권한 등급 (permission_level 미지정 시 사용)
DEFAULT_PERMISSION_LEVEL = 1


class ToolValidator:
    """새로 생성된 툴 코드가 OpenHarness 규격에 맞는지 검증하는 유틸리티.

    검증 항목:
    - 파이썬 문법(Syntax) 검사
    - BaseTool / BaseModel 참조 존재 여부
    - execute 메소드 시그니처: (self, arguments, context) 3개 인자
    - ToolResult 올바른 사용법: output/is_error 키워드만 허용
    - context.input_model 안티패턴 감지
    - 보안 위반 검사: 금지된 모듈/함수 사용 차단 (AST 정적 분석)
    """

    # 시스템을 위협할 수 있는 모듈 블랙리스트
    BANNED_MODULES: Set[str] = {
        "subprocess", "shutil", "socket", "ctypes",
        "multiprocessing", "signal", "pty", "resource",
    }

    # 시스템을 위협할 수 있는 함수/속성 블랙리스트
    BANNED_FUNCTIONS: Set[str] = {
        "system", "popen", "remove", "rmdir", "unlink",
        "rmtree", "exec", "eval", "compile", "execfile",
        "__import__", "makedirs", "rename", "replace",
        "chown", "chmod", "kill", "fork",
    }

    # ------------------------------------------------------------------
    # 1단계: 코드 문자열 정적 분석 (AST)
    # ------------------------------------------------------------------

    @classmethod
    def validate_code(cls, code: str) -> Tuple[bool, str]:
        """파이썬 코드의 문법과 OpenHarness 구조 규칙을 AST로 검사합니다."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax Error: {e}"

        if "BaseTool" not in code or "BaseModel" not in code:
            return False, (
                "코드 내에 BaseTool 또는 BaseModel 임포트/사용 내역이 "
                "없습니다."
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

        # 보안 위반 검사 (금지된 모듈/함수 사용 차단)
        cls._check_security_violations(tree, errors)

        if errors:
            return False, (
                "OpenHarness 규격 위반 감지:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        return True, "코드 문법 및 구조 검증 통과"

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
                    f"'{class_node.name}.execute()' 메소드의 인자가 "
                    f"{len(arg_names)}개입니다. "
                    f"올바른 형태: execute(self, arguments: <InputModel>, "
                    f"context: ToolExecutionContext) — 반드시 3개여야 합니다."
                )
                return

            if arg_names[0] != "self":
                errors.append(
                    f"'{class_node.name}.execute()' 첫 번째 인자는 "
                    f"'self'여야 합니다. (현재: '{arg_names[0]}')"
                )
            if arg_names[1] not in ("arguments", "args", "params", "input"):
                errors.append(
                    f"'{class_node.name}.execute()' 두 번째 인자는 "
                    f"파싱된 입력 모델을 받아야 합니다 (권장: 'arguments'). "
                    f"(현재: '{arg_names[1]}')"
                )
            if arg_names[2] != "context":
                errors.append(
                    f"'{class_node.name}.execute()' 세 번째 인자는 "
                    f"'context'여야 합니다. (현재: '{arg_names[2]}')"
                )
            return

        errors.append(
            f"'{class_node.name}' 클래스에 'execute' 메소드가 "
            f"정의되어 있지 않습니다."
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
                        "ToolResult.from_error()는 존재하지 않는 "
                        "메소드입니다. 대신 ToolResult(output=..., "
                        "is_error=True)를 사용하세요."
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
                            f"ToolResult()에 유효하지 않은 키워드 "
                            f"인자가 사용되었습니다: "
                            f"{', '.join(invalid_kws)}. "
                            f"허용 키워드: {', '.join(sorted(VALID_KEYWORDS))}"
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
                    "context.input_model은 존재하지 않습니다. "
                    "입력 데이터는 execute(self, arguments, context)의 "
                    "'arguments' 인자로 전달됩니다."
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
                        f"입력 모델명 충돌 방지를 위해, "
                        f"'{tool_class_name}'의 입력 모델 이름은 "
                        f"반드시 '{expected}'이어야 합니다. "
                        f"(현재: '{name}')"
                    )

    @classmethod
    def _check_security_violations(
        cls,
        tree: ast.Module,
        errors: List[str],
    ) -> None:
        """AST를 분석하여 시스템을 위협할 수 있는 코드 패턴을 차단합니다.

        검사 대상:
        - 금지된 모듈 임포트 (subprocess, shutil, socket 등)
        - 위험 함수 호출 (os.system, eval, exec, rmtree 등)
        - os 모듈의 파괴적 함수 (os.remove, os.rmdir, os.unlink 등)
        """
        for node in ast.walk(tree):
            # --- 모듈 임포트 검사 ---
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_module = alias.name.split(".")[0]
                    if top_module in cls.BANNED_MODULES:
                        errors.append(
                            f"보안 정책 위반: '{alias.name}' 모듈은 "
                            f"사용할 수 없습니다. "
                            f"(차단 사유: 시스템 파괴 위험)"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_module = node.module.split(".")[0]
                    if top_module in cls.BANNED_MODULES:
                        errors.append(
                            f"보안 정책 위반: '{node.module}' "
                            f"모듈에서의 임포트는 허용되지 않습니다. "
                            f"(차단 사유: 시스템 파괴 위험)"
                        )

            # --- 위험 함수 호출 검사 ---
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in cls.BANNED_FUNCTIONS:
                    errors.append(
                        f"보안 정책 위반: '{func_name}()' 함수는 "
                        f"호출할 수 없습니다. "
                        f"(차단 사유: 시스템 파괴 또는 코드 인젝션 위험)"
                    )

    # ------------------------------------------------------------------
    # 2단계: 모듈 로드 및 런타임 규격 검증
    # ------------------------------------------------------------------

    @classmethod
    def validate_and_load_module(
        cls, module_name: str, file_path: str
    ) -> Tuple[bool, str, Optional[Type[BaseTool]]]:
        """모듈을 동적으로 로드하고 BaseTool 규격을 완벽히 준수하는지 검증합니다."""
        if not os.path.exists(file_path):
            return False, "파일이 존재하지 않습니다.", None

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return False, "모듈 스펙을 로드할 수 없습니다.", None

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            return False, f"모듈 실행 중 에러 발생: {e}", None

        # BaseTool을 상속받은 클래스 탐색
        tool_classes = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseTool) and obj is not BaseTool:
                tool_classes.append(obj)

        if not tool_classes:
            return False, "BaseTool을 상속받은 클래스를 찾을 수 없습니다.", None

        tool_class = tool_classes[0]  # 첫 번째 발견된 툴 클래스 사용

        # OpenHarness 필수 속성(name, description, input_model) 검증
        if not hasattr(tool_class, "name") or not getattr(tool_class, "name"):
            return False, "툴 클래스에 'name' 속성이 없거나 비어 있습니다.", None
        if not hasattr(tool_class, "description") or not getattr(tool_class, "description"):
            return False, "툴 클래스에 'description' 속성이 없거나 비어 있습니다.", None
        if not hasattr(tool_class, "input_model") or not issubclass(
            tool_class.input_model, BaseModel
        ):
            return (
                False,
                "툴 클래스에 'input_model'이 정의되지 않았거나 BaseModel의 하위 클래스가 아닙니다.",
                None,
            )

        # execute 메소드 런타임 시그니처 검증
        execute_method = getattr(tool_class, "execute", None)
        if execute_method is None:
            return False, "execute 메소드가 정의되어 있지 않습니다.", None

        sig = inspect.signature(execute_method)
        params = list(sig.parameters.keys())
        # 바운드 메소드면 self 제외, 언바운드면 self 포함
        if params and params[0] == "self":
            params = params[1:]
        if len(params) != 2:
            return (
                False,
                f"execute 메소드의 인자가 올바르지 않습니다. "
                f"(self 제외 {len(params)}개). "
                f"올바른 형태: execute(self, arguments, context)",
                None,
            )

        return True, f"검증 성공: '{tool_class.name}' 툴 로드 완료", tool_class


# ---------------------------------------------------------------------------
# Dynamic Tool Loader
# ---------------------------------------------------------------------------


def load_custom_tools(
    registry: ToolRegistry,
    tool_permissions: Optional[Dict[str, int]] = None,
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
    loaded: List[str] = []

    if not os.path.isdir(CUSTOM_TOOLS_DIR):
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
    """create_tool 메타 툴의 입력 모델."""

    tool_name: str = Field(
        description="생성할 툴의 파일명 (예: weather_fetcher)"
    )
    python_code: str = Field(
        description=(
            "BaseTool과 BaseModel을 임포트하고 규격에 맞게 작성된 "
            "완전한 파이썬 코드 문자열. 반드시 BaseTool 상속 클래스에 "
            "permission_level 클래스 속성을 포함해야 합니다."
        )
    )
    permission_level: int = Field(
        default=1,
        description=(
            "이 툴을 사용하기 위해 필요한 최소 권한 레벨 (자연수). "
            "1=누구나, 값이 클수록 높은 권한 필요."
        ),
    )


class ToolCreatorTool(BaseTool):
    """새로운 Python 툴을 생성·검증·저장하고 즉시 사용 가능하게 등록합니다."""

    name = "create_tool"
    description = (
        "Create a new Python tool, validate its syntax and OpenHarness "
        "compliance, and save it to the custom_tools directory. On success, "
        "the tool is registered in the current session's ToolRegistry and "
        "available from the NEXT turn. "
        "CRITICAL: You CANNOT create a tool and call it in the SAME turn. "
        "You must call create_tool, wait for the success result, and ONLY "
        "THEN call the newly created tool in your next response."
    )
    input_model = ToolCreatorInput

    async def execute(
        self, arguments: ToolCreatorInput, context: ToolExecutionContext
    ) -> ToolResult:
        """툴 코드를 검증, 저장, 그리고 런타임 레지스트리에 즉시 주입합니다."""
        os.makedirs(CUSTOM_TOOLS_DIR, exist_ok=True)
        file_path = os.path.join(CUSTOM_TOOLS_DIR, f"{arguments.tool_name}.py")

        # 0. permission_level을 코드에 자동 삽입 (클래스 속성이 없는 경우)
        code = arguments.python_code
        if "permission_level" not in code:
            # 정규식: 클래스 내부의 'name = "..."' 패턴을 안전하게 타겟팅
            pattern = r'(\n\s+)name\s*=\s*(["\'][^"\']+["\'])'
            replacement = (
                r'\g<1>permission_level = '
                + str(arguments.permission_level)
                + r'\g<1>name = \2'
            )
            new_code = re.sub(pattern, replacement, code, count=1)
            if new_code == code:
                return ToolResult(
                    output=(
                        "❌ 클래스 내부에 'name = ...' 속성을 "
                        "찾을 수 없어 permission_level 자동 주입에 "
                        "실패했습니다. 코드에 permission_level을 "
                        "직접 포함해 주세요."
                    ),
                    is_error=True,
                )
            code = new_code

        # 1. 코드 문법 검증
        is_valid_code, code_msg = ToolValidator.validate_code(code)
        if not is_valid_code:
            return ToolResult(
                output=f"❌ 코드 문법/기본 구조 검증 실패:\n{code_msg}",
                is_error=True,
            )

        # 2. 파일 저장
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        # 3. 모듈 로드 및 구조(Schema) 검증
        is_valid_module, mod_msg, tool_class = ToolValidator.validate_and_load_module(
            arguments.tool_name, file_path
        )
        if not is_valid_module:
            # 검증 실패 시 생성된 파일 롤백(삭제)
            os.remove(file_path)
            return ToolResult(
                output=f"❌ 툴 규격 검증 실패 (파일 롤백됨):\n{mod_msg}",
                is_error=True,
            )

        # 4. 런타임 ToolRegistry 및 RBAC에 즉시 등록
        registry = context.metadata.get("tool_registry")
        tool_permissions = context.metadata.get("tool_permissions")
        level = getattr(tool_class, "permission_level", arguments.permission_level)

        if registry is not None and tool_class is not None:
            try:
                instance = tool_class()
                registry.register(instance)

                # RBAC 권한 맵에도 등록
                if tool_permissions is not None:
                    tool_permissions[tool_class.name] = level

                return ToolResult(
                    output=(
                        f"✅ 툴 '{tool_class.name}' 생성·검증·등록 완료!\n"
                        f"파일: {file_path}\n"
                        f"권한 등급: {level}\n"
                        f"⚡ 이 툴은 현재 세션에 즉시 등록되어 바로 사용할 수 있습니다."
                    )
                )
            except Exception as e:
                return ToolResult(
                    output=(
                        f"✅ 툴 파일은 저장되었지만, 런타임 등록 중 에러 발생: {e}\n"
                        f"파일: {file_path}\n"
                        f"다음 세션 시작 시 자동으로 로드됩니다."
                    )
                )

        return ToolResult(
            output=(
                f"✅ 툴 '{tool_class.name}' 생성 및 검증 완료!\n"
                f"파일: {file_path}\n"
                f"권한 등급: {level}\n"
                f"⚠️ 런타임 레지스트리에 접근할 수 없어 자동 등록은 건너뛰었습니다. "
                f"다음 세션 시작 시 자동으로 로드됩니다."
            )
        )

