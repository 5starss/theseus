from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.models.modes import AgentMode
from theseus_engine.models.state import TheseusStateMachine
from theseus_engine.core.tool_visibility import (
    ToolVisibilityPolicy,
    build_visible_registry,
    can_create_tool_for_state,
)
from theseus_engine.models.sessions import list_sessions, get_session_path, save_session_history, load_session_history

class TheseusCommandHandler:
    def __init__(self, engine: QueryEngine, sm: TheseusStateMachine, full_registry, project_tool_permissions: dict, user_level: int, current_session: str):
        self.engine = engine
        self.sm = sm
        self.full_registry = full_registry
        self.project_tool_permissions = project_tool_permissions
        self.user_level = user_level
        self.current_session = current_session

    def handle_command(self, user_input: str) -> tuple[bool, str]:
        """
        Returns a tuple: (handled: bool, message: str)
        If the command was recognized and handled, handled is True.
        """
        parts = user_input.lower().split()
        cmd = parts[0]
        args = parts[1:]

        if cmd == "/ask":
            self.sm.switch_mode(AgentMode.ASK)
            self._sync_engine_tool_visibility()
            return True, "\n[System] Switched to ASK mode (Read-only)."
            
        elif cmd == "/agent":
            self.sm.switch_mode(AgentMode.AGENT)
            self._sync_engine_tool_visibility()
            return True, "\n[System] Switched to AGENT mode."
            
        elif cmd == "/plan":
            self.sm.switch_mode(AgentMode.PLAN)
            self._sync_engine_tool_visibility()
            return True, "\n[System] Switched to PLAN mode (Drafting phase)."
            
        elif cmd == "/clear":
            if hasattr(self.engine, "_messages"):
                self.engine._messages = []
            session_path = get_session_path(self.current_session)
            if session_path.exists():
                session_path.unlink()
            return True, f"\n🧹 Session '{self.current_session}' history cleared."
            
        elif cmd == "/session":
            if not args:
                return True, "\n[Session] Usage: /session [list|new|switch] [name]"
            
            sub_cmd = args[0]
            if sub_cmd == "list":
                msg = "\n[Session] Available sessions:\n"
                for name in list_sessions():
                    prefix = " *" if name == self.current_session else "  "
                    msg += f"{prefix} {name}\n"
                return True, msg.strip()
                
            elif sub_cmd == "new" or sub_cmd == "switch":
                if len(args) < 2:
                    return True, f"\n[Session] Usage: /session {sub_cmd} <session_name>"
                
                new_session_name = args[1]
                try:
                    get_session_path(new_session_name) # Validate name
                except ValueError as e:
                    return True, f"\n[Error] {e}"
                    
                if hasattr(self.engine, "_messages") and self.engine._messages:
                    save_session_history(self.current_session, self.engine._messages)
                    
                self.current_session = new_session_name
                self.engine._messages = load_session_history(self.current_session)
                msg = f"\n✅ Switched to session '{self.current_session}'."
                if not self.engine._messages:
                     msg += "\nStarted a new empty session."
                return True, msg
            else:
                return True, f"\n[Session] Unknown command: {sub_cmd}. Use list, new, or switch."
                
        return False, "Unknown command."

    def _sync_engine_tool_visibility(self) -> None:
        can_create_tool = can_create_tool_for_state(
            mode=self.sm.mode,
            plan_phase=getattr(self.sm, "plan_phase", None),
            project_id=None,
            actor_role="ADMIN",
        )
        registry = build_visible_registry(
            self.full_registry,
            ToolVisibilityPolicy(
                mode=self.sm.mode,
                plan_phase=getattr(self.sm, "plan_phase", None),
                user_level=self.user_level,
                tool_permissions=self.project_tool_permissions,
                can_create_tool=can_create_tool,
            ),
        )
        self.engine.set_tool_registry(registry)
        self.engine.set_system_prompt(
            self.sm.get_system_prompt(
                available_tools=tuple(tool.name for tool in registry.list_tools())
            )
        )
