import os
import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from theseus_engine.engine.stream_events import (
    AssistantTextDelta, ToolExecutionStarted, ToolExecutionCompleted, ErrorEvent
)
from theseus_engine.models.modes import AgentMode
from theseus_engine.models.state import TheseusStateMachine
from theseus_engine.core.engine_builder import setup_engine
from theseus_engine.core.command_handler import TheseusCommandHandler
from theseus_engine.models.sessions import load_session_history, save_session_history

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
    
    project_tool_permissions = {
        "bash": 3, "read_file": 1, "write_file": 2, "edit_file": 2, 
        "glob": 1, "grep": 1, "web_search": 1, "web_fetch": 1,
        "dummy_echo": 1, "create_tool": 2, "system_reboot": 5,
    }
    user_level = 5
    
    sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
    engine, full_registry = await setup_engine(sm, user_level, project_tool_permissions, custom_permission_prompt)
    
    current_session = "default"
    print(f"✅ Active session: '{current_session}'")
    history_messages = load_session_history(current_session)
    if history_messages:
        print(f"🔄 Loaded {len(history_messages)} messages from session '{current_session}'.")
        engine._messages = history_messages

    command_handler = TheseusCommandHandler(
        engine, sm, full_registry, project_tool_permissions, user_level, current_session
    )

    # TODO: [Future Plan] CLI Auto-completion
    # Consider using 'prompt-toolkit' to implement command and file path auto-completion
    # similar to the Textual UI OptionList.
    
    while True:
        mode_prefix = f"[{sm.mode.value}] "
        session_prefix = f"{{{command_handler.current_session}}}"
        
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
            print(f"\n💾 Saving session '{command_handler.current_session}'...")
            if hasattr(engine, "_messages"):
                save_session_history(command_handler.current_session, engine._messages)
            break

        if user_input.startswith("/"):
            handled, msg = command_handler.handle_command(user_input)
            if handled:
                print(msg)
                continue
            else:
                print(msg)

        try:
            async for event in engine.submit_message(user_input):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="", flush=True)
                elif isinstance(event, ToolExecutionStarted):
                    print(f"\n> Executing tool: {event.tool_name}", flush=True)
                elif isinstance(event, ToolExecutionCompleted):
                    print(f"> Tool {event.tool_name} completed.", flush=True)
                    output_str = str(event.output)
                    if len(output_str) > 200:
                        output_str = output_str[:200] + "..."
                    print(f"> Output: {output_str}", flush=True)
                elif isinstance(event, ErrorEvent):
                    print(f"\n--- Error ---\n{event.message}\n------------", flush=True)
            print()
        except Exception as e:
            print(f"\n--- Unhandled Exception ---\n{e}\n-------------------------", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
