from pathlib import Path

class AutocompleteHelper:
    def __init__(self, bundle):
        self.bundle = bundle
        self.suggestion_mode = None

    def get_command_suggestions(self, filter_text: str):
        if not self.bundle: 
            return [], None
        
        commands = self.bundle.commands.list_commands()
        filtered = [cmd for cmd in commands if cmd.name.startswith(filter_text)]
        theseus_priority = {"plan", "agent", "ask", "session", "clear"}
        
        filtered.sort(key=lambda cmd: (0 if cmd.name in theseus_priority else 1, cmd.name))
        
        options = []
        if filtered:
            for cmd in filtered:
                prefix = "✨ " if cmd.name in theseus_priority else "  "
                desc = cmd.description
                if cmd.name == "plan" and "Switch to Theseus" not in desc:
                    desc = "Switch to Theseus PLAN mode"
                elif cmd.name == "agent" and "Switch to Theseus" not in desc:
                    desc = "Switch to Theseus AGENT mode"
                options.append(f"{prefix}/{cmd.name} - {desc}")
            self.suggestion_mode = "command"
            return options, "command"
        return [], None

    def get_file_suggestions(self, filter_text: str):
        cwd = Path.cwd()
        if "/" in filter_text:
            dirname, basename = filter_text.rsplit("/", 1)
            search_dir = cwd / dirname
        else:
            dirname, basename = "", filter_text
            search_dir = cwd

        if not search_dir.exists() or not search_dir.is_dir():
            return [], None

        try:
            entries = []
            for p in search_dir.iterdir():
                if p.name.startswith(basename):
                    if p.name.startswith(".") or p.name == "__pycache__":
                        continue
                    rel_path = str(p.relative_to(cwd)).replace("\\", "/")
                    if p.is_dir():
                        entries.append(f"@{rel_path}/")
                    else:
                        entries.append(f"@{rel_path}")
            entries.sort(key=lambda x: (not x.endswith("/"), x))
        except Exception:
            entries = []
            
        if entries:
            self.suggestion_mode = "file"
            return entries[:30], "file"
        return [], None

    def process_selection(self, option_text: str, current_value: str) -> str:
        """Returns the new input value after applying a suggestion."""
        if self.suggestion_mode == "command":
            clean_text = option_text.replace("✨", "").strip()
            cmd_name = clean_text.split(" ")[0]
            return cmd_name + " "
        elif self.suggestion_mode == "file":
            parts = current_value.split("@")
            replacement = option_text[1:]
            suffix = "" if replacement.endswith("/") else " "
            parts[-1] = replacement
            return "@".join(parts) + suffix
        return current_value
