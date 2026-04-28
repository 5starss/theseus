import os
import sys
import asyncio
import json
from pathlib import Path

# Add project root and OpenHarness/src to sys.path to allow running as script directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "OpenHarness" / "src"))

# Windows 터미널 인코딩 버그 패치
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# OpenHarness / Theseus imports
from openharness.api.openai_client import OpenAICompatibleClient
from openharness.engine.query_engine import QueryEngine
from openharness.engine.messages import ConversationMessage
from openharness.engine.stream_events import (
    AssistantTextDelta,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent
)
from openharness.tools import create_default_tool_registry

from theseus_engine.monkey_patches import apply_patches
from theseus_engine.state import TheseusStateMachine, AgentMode
from theseus_engine.tool_factory import (
    ToolCreatorTool, build_filtered_registry, load_custom_tools
)
from theseus_engine.tools import DummyTool, SystemRebootTool
from theseus_engine.rbac import TheseusPermissionChecker
from openharness.config.settings import PermissionSettings

from theseus_engine.sessions import (
    load_session_history, save_session_history, list_sessions, get_session_path
)

async def custom_permission_prompt(tool_name: str, reason: str) -> bool:
    prompt_msg = f"\n⚠️ [Security] The agent wants to execute '{tool_name}'.\nReason: {reason}\nAllow this action? (y/N): "
    
    while True:
        user_input = await asyncio.to_thread(input, prompt_msg)
        normalized_input = user_input.strip().lower()
        
        if normalized_input in ["y", "yes"]:
            return True
        elif normalized_input in ["n", "no"]:
            print("Action denied by user.")
            return False
        else:
            print("Invalid input. Please enter 'y' (yes) or 'n' (no).")
            prompt_msg = "Allow this action? (y/N): "

async def main():
    print("🚀 [Theseus] Starting Agent Loop with Native Permission Wrapper & Multi-turn Session Memory...")
    
    apply_patches()

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    if not base_url and "gemini" in model_name.lower():
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

    api_client = OpenAICompatibleClient(api_key=api_key, base_url=base_url)

    project_tool_permissions = {
        "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2, 
        "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
        "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
    }
    user_level = 5

    full_registry = create_default_tool_registry()
    full_registry.register(DummyTool())
    full_registry.register(SystemRebootTool())
    full_registry.register(ToolCreatorTool())

    loaded_tools = load_custom_tools(full_registry, project_tool_permissions)
    if loaded_tools:
        print(f"✅ Loaded {len(loaded_tools)} custom tools.")

    settings = PermissionSettings()
    permission_checker = TheseusPermissionChecker(settings, user_level, project_tool_permissions)
    
    sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)

    current_session = "default"
    print(f"✅ Active session: '{current_session}'")
    history_messages = load_session_history(current_session)
    if history_messages:
        print(f"🔄 Loaded {len(history_messages)} messages from session '{current_session}'.")

    engine = QueryEngine(
        api_client=api_client,
        tool_registry=build_filtered_registry(
            full_registry, project_tool_permissions, user_level, exclude_tools={"create_tool"}
        ),
        permission_checker=permission_checker,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=sm.get_system_prompt(),
        max_turns=30,
        permission_prompt=custom_permission_prompt,
        tool_metadata={
            "tool_registry": full_registry,
            "tool_permissions": project_tool_permissions,
        }
    )

    if history_messages and hasattr(engine, "_messages"):
        engine._messages = history_messages

    while True:
        mode_prefix = f"[{sm.mode.value}] "
        session_prefix = f"{{{current_session}}}"
        
        if sm.mode == AgentMode.PLAN and sm.plan_phase:
            mode_prefix = f"[{sm.mode.value}/{sm.plan_phase.value}] "
            
        try:
            user_input = await asyncio.to_thread(input, f"\n{session_prefix}{mode_prefix}> ")
            user_input = user_input.strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print(f"\n💾 Saving session '{current_session}'...")
            if hasattr(engine, "_messages"):
                save_session_history(current_session, engine._messages)
            break

        if user_input.startswith("/"):
            parts = user_input.lower().split()
            cmd = parts[0]
            args = parts[1:]

            if cmd == "/ask":
                sm.switch_mode(AgentMode.ASK)
                engine.set_system_prompt(sm.get_system_prompt())
                continue
            elif cmd == "/agent":
                sm.switch_mode(AgentMode.AGENT)
                engine._tool_registry = build_filtered_registry(
                    full_registry, project_tool_permissions, user_level, exclude_tools={"create_tool"}
                )
                engine.set_system_prompt(sm.get_system_prompt())
                continue
            elif cmd == "/plan":
                sm.switch_mode(AgentMode.PLAN)
                engine.set_system_prompt(sm.get_system_prompt())
                print("\n[System] Switched to PLAN mode (Drafting phase).")
                continue
            elif cmd == "/clear":
                if hasattr(engine, "_messages"):
                    engine._messages = []
                session_path = get_session_path(current_session)
                if session_path.exists():
                    session_path.unlink()
                print(f"\n🧹 Session '{current_session}' history cleared.")
                continue
            elif cmd == "/session":
                if not args:
                    print("\n[Session] Usage: /session [list|new|switch] [name]")
                    continue
                
                sub_cmd = args[0]
                if sub_cmd == "list":
                    print("\n[Session] Available sessions:")
                    for name in list_sessions():
                        prefix = " *" if name == current_session else "  "
                        print(f"{prefix} {name}")
                elif sub_cmd == "new" or sub_cmd == "switch":
                    if len(args) < 2:
                        print(f"\n[Session] Usage: /session {sub_cmd} <session_name>")
                        continue
                    
                    new_session_name = args[1]
                    try:
                        get_session_path(new_session_name) # Validate name
                    except ValueError as e:
                        print(f"\n[Error] {e}")
                        continue
                        
                    if hasattr(engine, "_messages") and engine._messages:
                        save_session_history(current_session, engine._messages)
                        
                    current_session = new_session_name
                    print(f"\n✅ Switched to session '{current_session}'.")
                    engine._messages = load_session_history(current_session)
                    if not engine._messages:
                         print("Started a new empty session.")
                else:
                    print(f"\n[Session] Unknown command: {sub_cmd}. Use list, new, or switch.")
                continue

        try:
            # The engine handles the full loop: user message -> tool calls -> tool results -> final response
            async for event in engine.submit_message(user_input):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="", flush=True)
                elif isinstance(event, ToolExecutionStarted):
                    print(f"\n> Executing tool: {event.tool_name}", flush=True)
                elif isinstance(event, ToolExecutionCompleted):
                    # The engine internally handles the result. We just display it.
                    print(f"> Tool {event.tool_name} completed.", flush=True)
                    output_str = str(event.output)
                    if len(output_str) > 200:
                        output_str = output_str[:200] + "..."
                    print(f"> Output: {output_str}", flush=True)
                elif isinstance(event, ErrorEvent):
                    print(f"\n--- Error ---\n{event.message}\n------------", flush=True)
            print() # Add a newline after the full response
        except Exception as e:
            print(f"\n--- Unhandled Exception ---\n{e}\n-------------------------", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
