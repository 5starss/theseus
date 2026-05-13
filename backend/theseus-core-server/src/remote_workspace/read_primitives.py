from __future__ import annotations

import shlex
from fnmatch import fnmatch
from collections.abc import Callable

from src.remote_workspace.exceptions import RemoteWorkspaceError
from src.remote_workspace.schemas import RemoteCommandResult, RemoteWorkspaceConnectionConfig
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from theseus_engine.tools.core.bash_tool import BashInput
from theseus_engine.tools.core.file_read_tool import ReadFileInput
from theseus_engine.tools.core.glob_tool import GlobInput
from theseus_engine.tools.core.grep_tool import GrepInput


ConnectorFactory = Callable[[RemoteWorkspaceConnectionConfig], SshRemoteWorkspaceConnector]

REMOTE_READ_ANALYSIS_TOOL_NAMES = frozenset({"read_file", "glob", "grep", "bash"})
DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS = 180


class RemoteWorkspaceToolMixin:
    """Builds guarded SSH connectors for Remote Workspace primitive tools."""

    def __init__(
        self,
        config: RemoteWorkspaceConnectionConfig,
        *,
        connector_factory: ConnectorFactory | None = None,
    ) -> None:
        self.config = config
        self.connector_factory = connector_factory or SshRemoteWorkspaceConnector

    def create_connector(self) -> SshRemoteWorkspaceConnector:
        return self.connector_factory(self.config)

    def format_command_failure(self, result: RemoteCommandResult) -> ToolResult:
        output = result.stderr.strip() or result.stdout.strip() or "Remote command failed."
        return ToolResult(output=output, is_error=True, metadata={"exit_code": result.exit_code})

    def format_remote_error(self, exc: Exception) -> ToolResult:
        return ToolResult(output=f"Remote Workspace tool failed: {type(exc).__name__}: {exc}", is_error=True)


class RemoteReadFileTool(RemoteWorkspaceToolMixin, BaseTool):
    name = "read_file"
    description = "Read a text file from the selected Remote Workspace with line numbers."
    input_model = ReadFileInput
    permission_level = 1
    is_destructive = False

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: ReadFileInput, context: ToolExecutionContext) -> ToolResult:
        del context
        connector = self.create_connector()
        try:
            remote_path = connector.resolve_path(arguments.path)
            end_line = arguments.offset + arguments.limit
            command = " ".join(
                [
                    f"if [ ! -e {shlex.quote(remote_path)} ]; then",
                    f"printf '%s\\n' {shlex.quote(f'File not found: {arguments.path}')}; exit 2;",
                    "fi;",
                    f"if [ -d {shlex.quote(remote_path)} ]; then",
                    f"printf '%s\\n' {shlex.quote(f'Cannot read directory: {arguments.path}')}; exit 3;",
                    "fi;",
                    (
                        "awk "
                        + shlex.quote(
                            f"NR > {arguments.offset} && NR <= {end_line} "
                            "{ printf \"%6d\\t%s\\n\", NR, $0 }"
                        )
                        + f" {shlex.quote(remote_path)}"
                    ),
                ]
            )
            result = connector.run_command(
                command,
                working_directory=".",
                timeout_seconds=DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
            )
            if result.exit_code != 0:
                return self.format_command_failure(result)
            output = result.stdout.strip()
            if not output:
                return ToolResult(output=f"(File is empty or offset out of range: {arguments.path})")
            header = (
                f"--- Reading remote:{arguments.path} "
                f"(Lines {arguments.offset + 1}-{arguments.offset + arguments.limit}) ---\n"
            )
            return ToolResult(output=header + output, metadata={"remote_path": remote_path})
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)


class RemoteGlobTool(RemoteWorkspaceToolMixin, BaseTool):
    name = "glob"
    description = "Find files in the selected Remote Workspace matching a glob pattern."
    input_model = GlobInput
    permission_level = 1
    is_destructive = False

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: GlobInput, context: ToolExecutionContext) -> ToolResult:
        del context
        connector = self.create_connector()
        try:
            root = connector.resolve_path(arguments.root)
            pattern = arguments.pattern.strip() or "*"
            command = f"find {shlex.quote(root)} -type f | sort | head -n 2000"
            result = connector.run_command(
                command,
                working_directory=".",
                timeout_seconds=DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
            )
            if result.exit_code != 0:
                return self.format_command_failure(result)
            files = [
                path
                for path in (
                    self.relative_remote_path(connector, line)
                    for line in result.stdout.splitlines()
                    if line.strip()
                )
                if fnmatch(path, pattern)
            ]
            if not files:
                return ToolResult(output=f"No matches found for pattern '{arguments.pattern}' in '{arguments.root}'")
            truncated = len(files) > 500
            visible_files = files[:500]
            return ToolResult(
                output=(
                    f"Found {len(visible_files)} matches:\n"
                    + "\n".join(visible_files)
                    + ("\n... (truncated)" if truncated else "")
                )
            )
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)

    def relative_remote_path(self, connector: SshRemoteWorkspaceConnector, path: str) -> str:
        normalized = path.strip()
        base_path = connector.base_path
        if normalized == base_path:
            return "."
        if normalized.startswith(f"{base_path}/"):
            return normalized[len(base_path) + 1 :]
        return normalized


class RemoteGrepTool(RemoteWorkspaceToolMixin, BaseTool):
    name = "grep"
    description = "Search for a pattern in file contents within the selected Remote Workspace."
    input_model = GrepInput
    permission_level = 1
    is_destructive = False

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: GrepInput, context: ToolExecutionContext) -> ToolResult:
        del context
        connector = self.create_connector()
        try:
            search_path = connector.resolve_path(arguments.path)
            grep_flags = "-Rn" if arguments.recursive else "-n"
            case_flag = "-i" if arguments.case_insensitive else ""
            command = (
                f"grep {grep_flags} {case_flag} --binary-files=without-match "
                f"-E -- {shlex.quote(arguments.query)} {shlex.quote(search_path)} | head -n 300"
            )
            result = connector.run_command(
                command,
                working_directory=".",
                timeout_seconds=DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
            )
            if result.exit_code != 0 and result.stderr.strip():
                return self.format_command_failure(result)
            matches = result.stdout.strip()
            if not matches:
                return ToolResult(output=f"No matches found for '{arguments.query}'")
            return ToolResult(output=f"Found remote matches:\n{matches}")
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)


class RemoteReadOnlyBashTool(RemoteWorkspaceToolMixin, BaseTool):
    name = "bash"
    description = "Run a read-only shell command in the selected Remote Workspace."
    input_model = BashInput
    permission_level = 1
    is_destructive = False

    READ_ONLY_COMMANDS = frozenset(
        {
            "awk",
            "cat",
            "df",
            "du",
            "find",
            "free",
            "grep",
            "head",
            "id",
            "journalctl",
            "lsof",
            "ls",
            "netstat",
            "ps",
            "pwd",
            "sed",
            "ss",
            "stat",
            "tail",
            "top",
            "uname",
            "uptime",
            "wc",
            "whoami",
        }
    )
    DENIED_TOKENS = (
        ">",
        ">>",
        "&&",
        ";",
        "| sh",
        "| bash",
        "`",
        "$(",
        " chmod ",
        " chown ",
        " cp ",
        " curl ",
        " dd ",
        " docker ",
        " kill ",
        " kubectl ",
        " mkdir ",
        " mv ",
        " npm ",
        " pip ",
        " pkill ",
        " python ",
        " reboot",
        " rm ",
        " rmdir ",
        " service ",
        " sudo ",
        " systemctl ",
        " tee ",
        " touch ",
        " truncate ",
        " wget ",
    )

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: BashInput, context: ToolExecutionContext) -> ToolResult:
        del context
        denied_reason = self.validate_read_only_command(arguments.command)
        if denied_reason:
            return ToolResult(output=denied_reason, is_error=True)

        connector = self.create_connector()
        try:
            result = connector.run_command(
                arguments.command,
                working_directory=arguments.cwd or ".",
                timeout_seconds=min(arguments.timeout_seconds, DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS),
            )
            if result.exit_code != 0:
                return self.format_command_failure(result)
            output = result.stdout.strip()
            if result.stderr.strip():
                output = f"{output}\n{result.stderr.strip()}".strip()
            return ToolResult(output=output or "(no output)", metadata={"exit_code": result.exit_code})
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)

    def validate_read_only_command(self, command: str) -> str | None:
        stripped = command.strip()
        if not stripped:
            return "Remote bash command must not be blank."
        try:
            command_parts = shlex.split(stripped)
        except ValueError as exc:
            return f"Remote bash command is invalid: {exc}"
        first_command = command_parts[0]
        if first_command not in self.READ_ONLY_COMMANDS:
            return f"Remote bash only allows read-only inspection commands. Command '{first_command}' is not allowed."

        lowered = f" {stripped.lower()} "
        for token in self.DENIED_TOKENS:
            if token in lowered:
                return f"Remote bash command contains a denied token: {token.strip()}"
        for part in command_parts[1:]:
            if part.startswith("/") and not self.is_under_base_path(part):
                return "Remote bash command path must stay under the Remote Workspace basePath."
        return None

    def is_under_base_path(self, path: str) -> bool:
        base_path = self.config.base_path.rstrip("/")
        if not base_path:
            return path.startswith("/")
        return path == base_path or path.startswith(f"{base_path}/")


def build_remote_read_analysis_tools(
    config: RemoteWorkspaceConnectionConfig,
    *,
    connector_factory: ConnectorFactory | None = None,
) -> list[BaseTool]:
    """Return Remote Workspace primitive tools using the existing LLM tool names."""

    return [
        RemoteReadFileTool(config, connector_factory=connector_factory),
        RemoteGlobTool(config, connector_factory=connector_factory),
        RemoteGrepTool(config, connector_factory=connector_factory),
        RemoteReadOnlyBashTool(config, connector_factory=connector_factory),
    ]
