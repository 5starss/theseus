import json
import difflib
import builtins
from typing import Any
from openharness.hooks.types import HookResult, AggregatedHookResult
from openharness.hooks.events import HookEvent

class SafeFileHook:
    """
    Hook to ensure file creation/modification actions are approved by the user.
    Uses PRE_TOOL_USE to intercept write_file and edit_file tools.
    """
    
    def __init__(self):
        self.type = "safe_file_hook"
        self.block_on_failure = True
        
    async def execute(self, event: HookEvent, payload: dict[str, Any]) -> HookResult:
        if event != HookEvent.PRE_TOOL_USE:
            return HookResult(hook_type=self.type, success=True)
            
        tool_name = payload.get("tool_name")
        if tool_name not in ["write_file", "edit_file", "create_tool"]:
            return HookResult(hook_type=self.type, success=True)
            
        tool_input = payload.get("tool_input", {})
        
        # Determine what we are doing
        if tool_name == "write_file":
            path = tool_input.get("path")
            content = tool_input.get("content", "")
            prompt_msg = (
                f"\n⚠️ [Security] The agent wants to create/overwrite a file:\n"
                f"Path: {path}\n"
                f"Content Preview:\n"
                f"{content[:500]}{'...' if len(content) > 500 else ''}\n"
                f"Allow this action? (y/N): "
            )
            
        elif tool_name == "edit_file":
            path = tool_input.get("path")
            old_str = tool_input.get("old_str", "")
            new_str = tool_input.get("new_str", "")
            
            # Simple diff
            diff = list(difflib.unified_diff(
                old_str.splitlines(keepends=True),
                new_str.splitlines(keepends=True),
                fromfile=f'a/{path}',
                tofile=f'b/{path}',
                n=3
            ))
            diff_str = "".join(diff) if diff else "(No differences found or unable to diff)"
            
            prompt_msg = (
                f"\n⚠️ [Security] The agent wants to edit a file:\n"
                f"Path: {path}\n"
                f"Diff:\n{diff_str}\n"
                f"Allow this action? (y/N): "
            )
            
        elif tool_name == "create_tool":
            tool_class_name = tool_input.get("tool_class_name")
            code = tool_input.get("code", "")
            prompt_msg = (
                f"\n⚠️ [Security] The agent wants to create a new tool:\n"
                f"Tool Name: {tool_class_name}\n"
                f"Code Preview:\n"
                f"{code[:500]}{'...' if len(code) > 500 else ''}\n"
                f"Allow this action? (y/N): "
            )
        
        # Interactive confirmation using asyncio.to_thread
        import asyncio
        try:
            # We must run `input()` in a thread to not block the async loop.
            user_input = await asyncio.to_thread(builtins.input, prompt_msg)
            user_input = user_input.strip().lower()
        except Exception:
            user_input = "n"
            
        if user_input in ["y", "yes"]:
            return HookResult(hook_type=self.type, success=True)
        else:
            return HookResult(
                hook_type=self.type, 
                success=False, 
                blocked=True, 
                reason="User denied the file modification action."
            )

class TheseusHookRegistry:
    def __init__(self):
        self.hooks = []
    
    def register(self, hook):
        self.hooks.append(hook)
        
    def get(self, event: HookEvent):
        return self.hooks

class TheseusHookExecutor:
    def __init__(self, registry):
        self._registry = registry
        
    async def execute(self, event: HookEvent, payload: dict[str, Any]) -> AggregatedHookResult:
        results = []
        for hook in self._registry.get(event):
            res = await hook.execute(event, payload)
            results.append(res)
        return AggregatedHookResult(results=results)
