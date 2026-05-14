from __future__ import annotations

import shlex
from fnmatch import fnmatch
from collections.abc import Callable

from pydantic import BaseModel, Field
from src.remote_workspace.exceptions import RemoteWorkspaceError
from src.remote_workspace.schemas import RemoteCommandResult, RemoteWorkspaceConnectionConfig
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from theseus_engine.tools.core.file_read_tool import ReadFileInput
from theseus_engine.tools.core.glob_tool import GlobInput
from theseus_engine.tools.core.grep_tool import GrepInput


ConnectorFactory = Callable[[RemoteWorkspaceConnectionConfig], SshRemoteWorkspaceConnector]

REMOTE_READ_ANALYSIS_TOOL_NAMES = frozenset(
    {
        "remote_read_file",
        "remote_grep",
        "remote_tail_log",
        "remote_check_cpu",
        "remote_check_memory",
        "remote_check_disk",
    }
)
DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS = 180


class RemoteTailLogInput(BaseModel):
    path: str = Field(description="Remote log file path relative to the Remote Workspace basePath.")
    lines: int = Field(default=200, ge=1, le=1000, description="Number of log lines to read from the end.")


class RemoteNoInput(BaseModel):
    pass


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
    name = "remote_read_file"
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
    name = "remote_glob"
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
    name = "remote_grep"
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


class RemoteTailLogTool(RemoteWorkspaceToolMixin, BaseTool):
    name = "remote_tail_log"
    description = "Read recent lines from a log file in the selected Remote Workspace."
    input_model = RemoteTailLogInput
    permission_level = 1
    is_destructive = False

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: RemoteTailLogInput, context: ToolExecutionContext) -> ToolResult:
        del context
        connector = self.create_connector()
        try:
            remote_path = connector.resolve_path(arguments.path)
            result = connector.run_command(
                f"tail -n {arguments.lines} {shlex.quote(remote_path)}",
                working_directory=".",
                timeout_seconds=DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
            )
            if result.exit_code != 0:
                return self.format_command_failure(result)
            return ToolResult(
                output=result.stdout.strip() or "(no log output)",
                metadata={"remote_path": remote_path, "lines": arguments.lines},
            )
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)


class RemoteResourceCheckTool(RemoteWorkspaceToolMixin, BaseTool):
    input_model = RemoteNoInput
    permission_level = 1
    is_destructive = False
    command = ""

    def is_read_only(self, arguments) -> bool:
        return True

    async def execute(self, arguments: RemoteNoInput, context: ToolExecutionContext) -> ToolResult:
        del arguments, context
        connector = self.create_connector()
        try:
            result = connector.run_command(
                self.command,
                working_directory=".",
                timeout_seconds=DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
            )
            if result.exit_code != 0:
                return self.format_command_failure(result)
            return ToolResult(output=result.stdout.strip() or "(no output)")
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)


class RemoteCheckCpuTool(RemoteResourceCheckTool):
    name = "remote_check_cpu"
    description = "Inspect CPU load and top processes in the selected Remote Workspace."
    command = "uptime && ps -eo pid,ppid,comm,%cpu,%mem --sort=-%cpu | head -n 15"


class RemoteCheckMemoryTool(RemoteResourceCheckTool):
    name = "remote_check_memory"
    description = "Inspect memory usage in the selected Remote Workspace."
    command = "free -m && ps -eo pid,ppid,comm,%mem,%cpu --sort=-%mem | head -n 15"


class RemoteCheckDiskTool(RemoteResourceCheckTool):
    name = "remote_check_disk"
    description = "Inspect disk usage in the selected Remote Workspace."
    command = "df -h"


def build_remote_read_analysis_tools(
    config: RemoteWorkspaceConnectionConfig,
    *,
    connector_factory: ConnectorFactory | None = None,
) -> list[BaseTool]:
    """Return Remote Workspace read-only primitive tools with explicit remote names."""

    return [
        RemoteReadFileTool(config, connector_factory=connector_factory),
        RemoteGrepTool(config, connector_factory=connector_factory),
        RemoteTailLogTool(config, connector_factory=connector_factory),
        RemoteCheckCpuTool(config, connector_factory=connector_factory),
        RemoteCheckMemoryTool(config, connector_factory=connector_factory),
        RemoteCheckDiskTool(config, connector_factory=connector_factory),
    ]
