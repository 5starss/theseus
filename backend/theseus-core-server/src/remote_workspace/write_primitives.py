from __future__ import annotations

import asyncio
import posixpath
import shlex

from src.remote_workspace.exceptions import RemoteWorkspaceError
from src.remote_workspace.read_primitives import (
    DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
    ConnectorFactory,
    RemoteWorkspaceToolMixin,
)
from src.remote_workspace.schemas import RemoteWorkspaceConnectionConfig
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from theseus_engine.tools.core.bash_tool import BashInput
from theseus_engine.tools.core.edit_safety import (
    build_overwrite_rejected_report,
    merge_preserve_patterns,
    render_blocked_message,
    render_success_message,
    validate_text_update,
)
from theseus_engine.tools.core.file_edit_tool import EditFileInput
from theseus_engine.tools.core.file_utils import _strip_markdown_links
from theseus_engine.tools.core.file_write_tool import WriteFileInput


REMOTE_WRITE_EXECUTION_TOOL_NAMES = frozenset(
    {"remote_write_file", "remote_edit_file", "remote_run_command"}
)


class RemoteWritableToolMixin(RemoteWorkspaceToolMixin):
    """Provides guarded SFTP helpers for Remote Workspace write primitive tools."""

    def write_remote_text(
        self,
        connector: SshRemoteWorkspaceConnector,
        remote_path: str,
        content: str,
    ) -> None:
        parent_path = posixpath.dirname(remote_path)
        mkdir_result = connector.run_command(
            f"mkdir -p {shlex.quote(parent_path)}",
            working_directory=".",
            timeout_seconds=DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS,
        )
        if mkdir_result.exit_code != 0:
            raise RemoteWorkspaceError(mkdir_result.stderr.strip() or "Remote directory creation failed.")

        client = connector.connect()
        try:
            sftp_client = client.open_sftp()
            try:
                with sftp_client.open(remote_path, "wb") as remote_file:
                    remote_file.write(content.encode("utf-8"))
            finally:
                sftp_client.close()
        finally:
            client.close()

    def read_remote_text(
        self,
        connector: SshRemoteWorkspaceConnector,
        remote_path: str,
    ) -> str:
        client = connector.connect()
        try:
            sftp_client = client.open_sftp()
            try:
                with sftp_client.open(remote_path, "rb") as remote_file:
                    raw_content = remote_file.read()
            finally:
                sftp_client.close()
        finally:
            client.close()

        if isinstance(raw_content, bytes):
            return raw_content.decode("utf-8")
        return str(raw_content)

    def remove_remote_file(
        self,
        connector: SshRemoteWorkspaceConnector,
        remote_path: str,
    ) -> None:
        client = connector.connect()
        try:
            sftp_client = client.open_sftp()
            try:
                sftp_client.remove(remote_path)
            finally:
                sftp_client.close()
        finally:
            client.close()

    def strip_code_markdown_links(self, path: str, content: str) -> str:
        if path.endswith((".py", ".ts", ".js", ".tsx", ".jsx", ".sh")):
            return _strip_markdown_links(content)
        return content


class RemoteWriteFileTool(RemoteWritableToolMixin, BaseTool):
    name = "remote_write_file"
    description = "Create or overwrite a file in the selected Remote Workspace."
    input_model = WriteFileInput
    permission_level = 2
    is_destructive = True

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(self, arguments: WriteFileInput, context: ToolExecutionContext) -> ToolResult:
        connector = self.create_connector()
        try:
            remote_path = connector.resolve_path(arguments.path)
            content = self.strip_code_markdown_links(arguments.path, arguments.content)
            preserve_patterns = merge_preserve_patterns(
                arguments.preserve_patterns,
                context.metadata,
            )
            existed_before = False
            original_content = ""
            try:
                original_content = await asyncio.to_thread(
                    self.read_remote_text,
                    connector,
                    remote_path,
                )
                existed_before = True
            except FileNotFoundError:
                existed_before = False

            if existed_before and (
                not arguments.allow_overwrite or not (arguments.overwrite_reason or "").strip()
            ):
                report = build_overwrite_rejected_report(
                    path=f"remote:{arguments.path}",
                    old_content=original_content,
                    new_content=content,
                    operation="remote_write_file",
                )
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"remote_path": remote_path, "safetyReport": report.to_metadata()},
                )

            report = validate_text_update(
                path=arguments.path,
                old_content=original_content,
                new_content=content,
                operation="remote_write_file",
                expected_change="overwrite" if existed_before else "add_only",
                preserve_patterns=preserve_patterns,
            )
            if not report.allowed:
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"remote_path": remote_path, "safetyReport": report.to_metadata()},
                )
            await asyncio.to_thread(
                self.write_remote_text,
                connector,
                remote_path,
                content,
            )
            try:
                written = await asyncio.to_thread(
                    self.read_remote_text,
                    connector,
                    remote_path,
                )
                post_report = validate_text_update(
                    path=arguments.path,
                    old_content=original_content,
                    new_content=written,
                    operation="remote_write_file",
                    expected_change="overwrite" if existed_before else "add_only",
                    preserve_patterns=preserve_patterns,
                )
                if not post_report.allowed:
                    if existed_before:
                        await asyncio.to_thread(
                            self.write_remote_text,
                            connector,
                            remote_path,
                            original_content,
                        )
                    else:
                        await asyncio.to_thread(
                            self.remove_remote_file,
                            connector,
                            remote_path,
                        )
                    post_report.mark_rolled_back()
                    return ToolResult(
                        output=render_blocked_message(post_report),
                        is_error=True,
                        metadata={"remote_path": remote_path, "safetyReport": post_report.to_metadata()},
                    )
                report = post_report
            except Exception as verify_error:
                if existed_before:
                    await asyncio.to_thread(
                        self.write_remote_text,
                        connector,
                        remote_path,
                        original_content,
                    )
                else:
                    try:
                        await asyncio.to_thread(
                            self.remove_remote_file,
                            connector,
                            remote_path,
                        )
                    except Exception:
                        pass
                report.violations.append(f"post-write verification failed: {verify_error}")
                report.mark_rolled_back()
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"remote_path": remote_path, "safetyReport": report.to_metadata()},
                )
            return ToolResult(
                output=render_success_message(
                    report=report,
                    action=f"Successfully wrote {len(content.encode('utf-8'))} bytes to remote:{arguments.path}",
                    detail="Existing remote file overwritten." if existed_before else "New remote file created.",
                ),
                metadata={"remote_path": remote_path, "safetyReport": report.to_metadata()},
            )
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)
        except OSError as exc:
            return ToolResult(output=f"Remote file write failed: {exc}", is_error=True)
        except UnicodeError as exc:
            return ToolResult(output=f"Remote file content encoding failed: {exc}", is_error=True)


class RemoteEditFileTool(RemoteWritableToolMixin, BaseTool):
    name = "remote_edit_file"
    description = "Edit a remote file by replacing a specific text block with new content."
    input_model = EditFileInput
    permission_level = 2
    is_destructive = True

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(self, arguments: EditFileInput, context: ToolExecutionContext) -> ToolResult:
        connector = self.create_connector()
        try:
            remote_path = connector.resolve_path(arguments.path)
            preserve_patterns = merge_preserve_patterns(
                arguments.preserve_patterns,
                context.metadata,
            )
            content = await asyncio.to_thread(
                self.read_remote_text,
                connector,
                remote_path,
            )
            old_string = self.strip_code_markdown_links(arguments.path, arguments.old_str)
            new_string = self.strip_code_markdown_links(arguments.path, arguments.new_str)
            if old_string not in content:
                return ToolResult(
                    output=(
                        f"Error: The provided 'old_str' was not found in remote:{arguments.path}. "
                        "Ensure exact match including whitespace."
                    ),
                    is_error=True,
                )
            occurrences = content.count(old_string)
            if occurrences != 1 and not arguments.replace_all:
                return ToolResult(
                    output=(
                        f"Error: The provided 'old_str' matched {occurrences} locations "
                        f"in remote:{arguments.path}. Use a more specific old_str or set "
                        "replace_all=true only when all matches are intended."
                    ),
                    is_error=True,
                )

            replace_count = -1 if arguments.replace_all else 1
            updated_content = content.replace(old_string, new_string, replace_count)
            report = validate_text_update(
                path=arguments.path,
                old_content=content,
                new_content=updated_content,
                operation="remote_edit_file",
                expected_change=arguments.expected_change,
                preserve_patterns=preserve_patterns,
            )
            if not report.allowed:
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"remote_path": remote_path, "safetyReport": report.to_metadata()},
                )
            await asyncio.to_thread(
                self.write_remote_text,
                connector,
                remote_path,
                updated_content,
            )
            try:
                written = await asyncio.to_thread(
                    self.read_remote_text,
                    connector,
                    remote_path,
                )
                post_report = validate_text_update(
                    path=arguments.path,
                    old_content=content,
                    new_content=written,
                    operation="remote_edit_file",
                    expected_change=arguments.expected_change,
                    preserve_patterns=preserve_patterns,
                )
                if not post_report.allowed:
                    await asyncio.to_thread(
                        self.write_remote_text,
                        connector,
                        remote_path,
                        content,
                    )
                    post_report.mark_rolled_back()
                    return ToolResult(
                        output=render_blocked_message(post_report),
                        is_error=True,
                        metadata={"remote_path": remote_path, "safetyReport": post_report.to_metadata()},
                    )
                report = post_report
            except Exception as verify_error:
                await asyncio.to_thread(
                    self.write_remote_text,
                    connector,
                    remote_path,
                    content,
                )
                report.violations.append(f"post-write verification failed: {verify_error}")
                report.mark_rolled_back()
                return ToolResult(
                    output=render_blocked_message(report),
                    is_error=True,
                    metadata={"remote_path": remote_path, "safetyReport": report.to_metadata()},
                )
            actual_replaces = occurrences if arguments.replace_all else 1
            return ToolResult(
                output=render_success_message(
                    report=report,
                    action=f"Successfully updated remote:{arguments.path}.",
                    detail=f"Replacements made: {actual_replaces}",
                ),
                metadata={
                    "remote_path": remote_path,
                    "replace_count": actual_replaces,
                    "safetyReport": report.to_metadata(),
                },
            )
        except FileNotFoundError:
            return ToolResult(output=f"File not found: remote:{arguments.path}", is_error=True)
        except UnicodeDecodeError as exc:
            return ToolResult(output=f"Remote file is not valid UTF-8 text: {exc}", is_error=True)
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)
        except OSError as exc:
            return ToolResult(output=f"Remote file edit failed: {exc}", is_error=True)


class RemoteRunCommandTool(RemoteWorkspaceToolMixin, BaseTool):
    name = "remote_run_command"
    description = "Run a guarded shell command in the selected Remote Workspace."
    input_model = BashInput
    permission_level = 3
    is_destructive = True

    DENIED_COMMANDS = frozenset(
        {
            "dd",
            "bash",
            "cd",
            "fish",
            "halt",
            "mkfs",
            "pkill",
            "poweroff",
            "reboot",
            "rm",
            "rmdir",
            "sh",
            "shutdown",
            "su",
            "sudo",
            "unlink",
            "zsh",
        }
    )
    DENIED_PATTERNS = (
        " rm -rf /",
        " rm -fr /",
        " chmod -r 777 /",
        " chmod 777 /",
        " chown -r ",
        " && ",
        " || ",
        " ; ",
        "| sh",
        "| bash",
        "\n",
        "`",
        "$(",
    )
    DENIED_RAW_OPERATORS = ("&&", "||", ";", "\n", "`", "$(")
    SHELL_COMMANDS = frozenset({"bash", "fish", "sh", "zsh"})

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(self, arguments: BashInput, context: ToolExecutionContext) -> ToolResult:
        del context
        denied_reason = self.validate_guarded_command(arguments.command)
        if denied_reason:
            return ToolResult(output=denied_reason, is_error=True)

        connector = self.create_connector()
        try:
            result = await asyncio.to_thread(
                connector.run_command,
                arguments.command,
                working_directory=arguments.cwd or ".",
                timeout_seconds=min(arguments.timeout_seconds, DEFAULT_REMOTE_COMMAND_TIMEOUT_SECONDS),
            )
            output = result.stdout.strip()
            if result.stderr.strip():
                output = f"{output}\n{result.stderr.strip()}".strip()
            return ToolResult(
                output=output or "(no output)",
                is_error=result.exit_code != 0,
                metadata={"exit_code": result.exit_code, "remote_workspace": True},
            )
        except RemoteWorkspaceError as exc:
            return self.format_remote_error(exc)

    def validate_guarded_command(self, command: str) -> str | None:
        stripped_command = command.strip()
        if not stripped_command:
            return "Remote bash command must not be blank."
        try:
            command_parts = shlex.split(stripped_command)
        except ValueError as exc:
            return f"Remote bash command is invalid: {exc}"

        first_command = command_parts[0]
        if first_command.startswith("/"):
            return "Remote bash command must use command names, not absolute executable paths."
        if first_command in self.DENIED_COMMANDS:
            return f"Remote bash command '{first_command}' is not allowed."

        lowered_command = f" {stripped_command.lower()} "
        for operator in self.DENIED_RAW_OPERATORS:
            if operator in stripped_command:
                return f"Remote bash command contains a denied operator: {operator}"
        if "|" in stripped_command:
            pipe_segments = [segment.strip() for segment in stripped_command.split("|")]
            for segment in pipe_segments[1:]:
                if not segment:
                    return "Remote bash command contains an empty pipe segment."
                try:
                    segment_command = shlex.split(segment)[0]
                except (IndexError, ValueError):
                    return "Remote bash command contains an invalid pipe segment."
                if segment_command in self.SHELL_COMMANDS:
                    return "Remote bash command cannot pipe content into a shell."
            if " curl " in lowered_command or " wget " in lowered_command:
                return "Remote bash command cannot pipe downloaded content into another command."
        for pattern in self.DENIED_PATTERNS:
            if pattern in lowered_command:
                return f"Remote bash command contains a denied pattern: {pattern.strip()}"

        for part in command_parts[1:]:
            if part.startswith("~"):
                return "Remote bash command path must not use home-directory expansion."
            if not self.is_allowed_command_path_argument(part):
                return "Remote bash command path must stay under the Remote Workspace basePath."
        return None

    def is_allowed_command_path_argument(self, argument: str) -> bool:
        if argument.startswith("-") or "://" in argument:
            return True
        if not (argument.startswith("/") or argument.startswith(".") or "/" in argument):
            return True
        if argument.startswith("/"):
            candidate = argument
        else:
            candidate = posixpath.join(self.config.base_path, argument)
        return self.is_under_base_path(candidate)

    def is_under_base_path(self, path: str) -> bool:
        base_path = posixpath.normpath(self.config.base_path).rstrip("/")
        normalized_path = posixpath.normpath(path)
        if not base_path:
            return normalized_path.startswith("/")
        return normalized_path == base_path or normalized_path.startswith(f"{base_path}/")


def build_remote_write_execution_tools(
    config: RemoteWorkspaceConnectionConfig,
    *,
    connector_factory: ConnectorFactory | None = None,
) -> list[BaseTool]:
    """Return Remote Workspace write/execute tools with explicit remote names."""

    return [
        RemoteWriteFileTool(config, connector_factory=connector_factory),
        RemoteEditFileTool(config, connector_factory=connector_factory),
        RemoteRunCommandTool(config, connector_factory=connector_factory),
    ]
