import inspect
import json
import os
import sys
import traceback
import types

INPUT_PATH = "/sandbox/input/payload.json"
CODE_PATH = "/sandbox/input/tool_code.py"
RESULT_PATH = "/sandbox/output/result.json"


def _write_result(payload: dict) -> None:
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def _install_stubs() -> type:
    pydantic_module = types.ModuleType("pydantic")

    class BaseModel:
        pass

    def Field(*args, **kwargs):
        del args, kwargs
        return None

    pydantic_module.BaseModel = BaseModel
    pydantic_module.Field = Field
    sys.modules["pydantic"] = pydantic_module

    openharness_module = types.ModuleType("openharness")
    tools_module = types.ModuleType("openharness.tools")
    base_module = types.ModuleType("openharness.tools.base")

    class BaseTool:
        pass

    class ToolExecutionContext:
        pass

    class ToolResult:
        def __init__(self, output=None, is_error=False, metadata=None):
            self.output = output
            self.is_error = is_error
            self.metadata = metadata

    class ToolRegistry:
        pass

    base_module.BaseTool = BaseTool
    base_module.ToolExecutionContext = ToolExecutionContext
    base_module.ToolResult = ToolResult
    base_module.ToolRegistry = ToolRegistry
    tools_module.base = base_module
    openharness_module.tools = tools_module

    sys.modules["openharness"] = openharness_module
    sys.modules["openharness.tools"] = tools_module
    sys.modules["openharness.tools.base"] = base_module
    return BaseTool


def _find_tool_class(namespace: dict, base_tool_cls: type) -> type:
    candidates = []
    for obj in namespace.values():
        if isinstance(obj, type) and issubclass(obj, base_tool_cls) and obj is not base_tool_cls:
            candidates.append(obj)
    if not candidates:
        raise RuntimeError("No BaseTool subclass was found in the generated module.")
    return candidates[0]


def main() -> int:
    try:
        with open(INPUT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)

        namespace: dict = {"__name__": "__sandbox_tool__"}
        base_tool_cls = _install_stubs()
        with open(CODE_PATH, "r", encoding="utf-8") as f:
            code = compile(f.read(), CODE_PATH, "exec")
        exec(code, namespace)

        tool_class = _find_tool_class(namespace, base_tool_cls)
        tool_instance = tool_class()

        execute_method = getattr(tool_instance, "execute", None)
        if execute_method is None:
            raise RuntimeError("Tool class is missing execute().")

        signature = inspect.signature(execute_method)
        params = list(signature.parameters.keys())
        if params and params[0] == "self":
            params = params[1:]
        if len(params) != 2:
            raise RuntimeError("execute() must accept exactly 2 parameters after self.")

        for attr in ("name", "description", "input_model"):
            if not getattr(tool_class, attr, None):
                raise RuntimeError(f"Tool class is missing required attribute: {attr}")

        _write_result(
            {
                "success": True,
                "result": {
                    "tool_name": getattr(tool_class, "name", payload.get("tool_name")),
                    "tool_class": tool_class.__name__,
                    "module_name": payload.get("module_name"),
                    "signature": str(signature),
                },
            }
        )
        return 0
    except Exception as exc:
        _write_result(
            {
                "success": False,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
