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

    theseus_engine_module = types.ModuleType("theseus_engine")
    theseus_tools_module = types.ModuleType("theseus_engine.tools")
    core_module = types.ModuleType("theseus_engine.tools.core")
    base_module = types.ModuleType("theseus_engine.tools.core.base_tools")

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
    core_module.base_tools = base_module
    theseus_tools_module.core = core_module
    theseus_engine_module.tools = theseus_tools_module

    src_module = types.ModuleType("src")
    remote_workspace_module = types.ModuleType("src.remote_workspace")
    runtime_module = types.ModuleType("src.remote_workspace.runtime")

    class RemoteWorkspaceRuntimeError(RuntimeError):
        pass

    def get_remote_workspace_config(context):
        del context
        return None

    def require_remote_workspace(context):
        del context
        raise RemoteWorkspaceRuntimeError("Remote Workspace is not available in sandbox validation.")

    def run_remote_command(*args, **kwargs):
        del args, kwargs
        raise RemoteWorkspaceRuntimeError("Remote Workspace command execution is disabled in sandbox validation.")

    runtime_module.RemoteWorkspaceRuntimeError = RemoteWorkspaceRuntimeError
    runtime_module.get_remote_workspace_config = get_remote_workspace_config
    runtime_module.require_remote_workspace = require_remote_workspace
    runtime_module.run_remote_command = run_remote_command
    remote_workspace_module.runtime = runtime_module
    src_module.remote_workspace = remote_workspace_module

    sys.modules["theseus_engine"] = theseus_engine_module
    sys.modules["theseus_engine.tools"] = theseus_tools_module
    sys.modules["theseus_engine.tools.core"] = core_module
    sys.modules["theseus_engine.tools.core.base_tools"] = base_module
    sys.modules["src"] = src_module
    sys.modules["src.remote_workspace"] = remote_workspace_module
    sys.modules["src.remote_workspace.runtime"] = runtime_module
    return BaseTool


def _find_tool_class(namespace: dict, base_tool_cls: type) -> type:
    candidates = []
    for obj in namespace.values():
        if isinstance(obj, type) and issubclass(obj, base_tool_cls) and obj is not base_tool_cls:
            candidates.append(obj)
    if not candidates:
        defined_classes = sorted(
            obj.__name__
            for obj in namespace.values()
            if isinstance(obj, type) and obj is not base_tool_cls
        )
        hint = ", ".join(defined_classes) if defined_classes else "none"
        raise RuntimeError(
            "No BaseTool subclass was found in the generated module. "
            f"Defined classes: {hint}."
        )
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
        missing_attrs = [
            attr for attr in ("name", "description", "input_model")
            if not getattr(tool_class, attr, None)
        ]
        if missing_attrs:
            raise RuntimeError(
                f"Tool class {tool_class.__name__} is missing required class "
                f"attributes: {', '.join(missing_attrs)}."
            )

        tool_instance = tool_class()

        execute_method = getattr(tool_instance, "execute", None)
        if execute_method is None or not callable(execute_method):
            raise RuntimeError(
                f"Tool class {tool_class.__name__} is missing callable "
                "execute(self, arguments, context)."
            )

        signature = inspect.signature(execute_method)
        params = list(signature.parameters.keys())
        if params and params[0] == "self":
            params = params[1:]
        if len(params) != 2:
            raise RuntimeError(
                f"{tool_class.__name__}.execute must accept exactly 2 parameters "
                "after self: arguments and context. "
                f"Actual signature: {signature}; parameters after self: {params}."
            )

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
