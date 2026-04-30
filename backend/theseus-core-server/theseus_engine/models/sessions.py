import json
from pathlib import Path
from typing import List
from openharness.engine.messages import ConversationMessage

# Session History Management
SESSION_DIR = Path(".theseus_sessions")
SESSION_DIR.mkdir(exist_ok=True)

def get_session_path(session_name: str) -> Path:
    """Get the file path for a given session name."""
    if not session_name or not session_name.isalnum():
        raise ValueError("Session name must be alphanumeric.")
    return SESSION_DIR / f"{session_name}.json"

def list_sessions() -> List[str]:
    """List all available session names."""
    return [p.stem for p in SESSION_DIR.glob("*.json")]

def load_session_history(session_name: str) -> List[ConversationMessage]:
    """Load conversation history from a specific session file."""
    session_file = get_session_path(session_name)
    if not session_file.exists():
        return []
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        messages = []
        for msg_dict in data:
            role = msg_dict.get("role", "user")
            content = msg_dict.get("content", [])
            msg = ConversationMessage(role=role, content=content)
            if "_raw_tool_calls" in msg_dict:
                object.__setattr__(msg, "_raw_tool_calls", msg_dict["_raw_tool_calls"])
            messages.append(msg)
        return messages
    except Exception as e:
        print(f"⚠️ Failed to load session history for '{session_name}': {e}")
        return []

def save_session_history(session_name: str, messages: List[ConversationMessage]):
    """Save conversation history to a specific session file."""
    session_file = get_session_path(session_name)
    try:
        data = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": []}
            for block in msg.content:
                if hasattr(block, "model_dump"):
                    msg_dict["content"].append(block.model_dump())
                elif hasattr(block, "dict"):
                    msg_dict["content"].append(block.dict())
                else:
                    msg_dict["content"].append(block)
                    
            if hasattr(msg, "_raw_tool_calls"):
                msg_dict["_raw_tool_calls"] = getattr(msg, "_raw_tool_calls")
            data.append(msg_dict)
            
        session_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Failed to save session history for '{session_name}': {e}")
