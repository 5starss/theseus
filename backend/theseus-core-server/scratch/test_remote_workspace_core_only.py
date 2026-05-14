from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("ALLOWED_ORIGINS", '["http://localhost:3000"]')

from pydantic import ValidationError

from src.builder.engine import _resolve_excluded_tools
from src.remote_workspace.read_primitives import (
    REMOTE_READ_ANALYSIS_TOOL_NAMES,
    build_remote_read_analysis_tools,
)
from src.remote_workspace.runtime import (
    REMOTE_WORKSPACE_RUNTIME_KEY,
    RemoteWorkspaceRuntimeError,
    get_remote_workspace_config,
    register_remote_workspace_config,
)
from src.remote_workspace.schemas import RemoteWorkspaceConnectionConfig
from src.remote_workspace.write_primitives import (
    REMOTE_WRITE_EXECUTION_TOOL_NAMES,
    RemoteRunCommandTool,
    build_remote_write_execution_tools,
)
from theseus_engine.models.state import AgentMode, PlanPhase
from theseus_engine.tools.core import ALL_CORE_TOOLS
from theseus_engine.tools.core.base_tools import ToolExecutionContext, ToolRegistry


def _remote_config(*, allow_write: bool = False) -> RemoteWorkspaceConnectionConfig:
    return RemoteWorkspaceConnectionConfig.model_validate(
        {
            "remoteWorkspaceId": 1,
            "projectId": 10,
            "host": "example.internal",
            "port": 22,
            "username": "ubuntu",
            "password": "secret-password",
            "basePath": "/srv/app",
            "allowWriteExecution": allow_write,
            "status": "ACTIVE",
        }
    )


def _registry_with_remote(config: RemoteWorkspaceConnectionConfig) -> ToolRegistry:
    registry = ToolRegistry()
    for tool_cls in ALL_CORE_TOOLS:
        registry.register(tool_cls())
    for tool in build_remote_read_analysis_tools(config):
        registry.register(tool)
    for tool in build_remote_write_execution_tools(config):
        registry.register(tool)
    return registry


def _allowed_tools(
    *,
    mode: AgentMode,
    allow_write: bool,
    plan_phase: PlanPhase | None = None,
) -> set[str]:
    config = _remote_config(allow_write=allow_write)
    registry = _registry_with_remote(config)
    excluded = _resolve_excluded_tools(
        mode,
        plan_phase,
        registry,
        has_remote_workspace=True,
        allow_remote_write_execution=mode == AgentMode.AGENT and allow_write,
    )
    return {tool.name for tool in registry.list_tools()} - excluded


class RemoteWorkspaceCoreOnlySmokeTest(unittest.TestCase):
    def test_redacted_dump_does_not_expose_secret_fields(self) -> None:
        config = _remote_config()
        redacted = config.redacted_model_dump(by_alias=True)
        key_config = RemoteWorkspaceConnectionConfig.model_validate(
            {
                "remoteWorkspaceId": 2,
                "projectId": 10,
                "host": "example.internal",
                "port": 22,
                "username": "ubuntu",
                "privateKeyPath": "/home/ubuntu/.ssh/id_rsa",
                "basePath": "/srv/app",
                "status": "ACTIVE",
            }
        )
        key_redacted = key_config.redacted_model_dump(by_alias=True)

        self.assertEqual(redacted["password"], "***")
        self.assertEqual(redacted["privateKeyPath"], None)
        self.assertNotEqual(redacted["password"], "secret-password")
        self.assertEqual(key_redacted["password"], None)
        self.assertEqual(key_redacted["privateKeyPath"], "***")
        self.assertNotEqual(key_redacted["privateKeyPath"], "/home/ubuntu/.ssh/id_rsa")

    def test_runtime_helper_uses_private_key_not_redacted_metadata(self) -> None:
        config = _remote_config()
        runtime_key = register_remote_workspace_config(config)
        context = ToolExecutionContext(
            cwd=Path(os.getcwd()),
            metadata={
                REMOTE_WORKSPACE_RUNTIME_KEY: runtime_key,
                "remote_workspace": config.redacted_model_dump(by_alias=True),
            },
        )

        self.assertIs(get_remote_workspace_config(context), config)

        redacted_only_context = ToolExecutionContext(
            cwd=Path(os.getcwd()),
            metadata={"remote_workspace": config.redacted_model_dump(by_alias=True)},
        )
        with self.assertRaises(RemoteWorkspaceRuntimeError):
            get_remote_workspace_config(redacted_only_context)

    def test_invalid_remote_workspace_config_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RemoteWorkspaceConnectionConfig.model_validate(
                {
                    "host": "example.internal",
                    "username": "ubuntu",
                    "password": "secret-password",
                    "basePath": "/",
                    "status": "ACTIVE",
                }
            )
        with self.assertRaises(ValidationError):
            RemoteWorkspaceConnectionConfig.model_validate(
                {
                    "host": "example.internal",
                    "username": "ubuntu",
                    "password": "secret-password",
                    "basePath": "/srv/app",
                    "status": "DISABLED",
                }
            )
        with self.assertRaises(ValidationError):
            RemoteWorkspaceConnectionConfig.model_validate(
                {
                    "host": "example.internal",
                    "username": "ubuntu",
                    "basePath": "/srv/app",
                    "status": "ACTIVE",
                }
            )

    def test_mode_filtered_remote_tool_visibility(self) -> None:
        ask_tools = _allowed_tools(mode=AgentMode.ASK, allow_write=True)
        plan_tools = _allowed_tools(
            mode=AgentMode.PLAN,
            allow_write=True,
            plan_phase=PlanPhase.DRAFTING,
        )
        agent_read_tools = _allowed_tools(mode=AgentMode.AGENT, allow_write=False)
        agent_write_tools = _allowed_tools(mode=AgentMode.AGENT, allow_write=True)

        self.assertTrue(
            REMOTE_READ_ANALYSIS_TOOL_NAMES.issubset(ask_tools),
            f"ask_tools={sorted(ask_tools)} expected={sorted(REMOTE_READ_ANALYSIS_TOOL_NAMES)}",
        )
        self.assertTrue(
            REMOTE_READ_ANALYSIS_TOOL_NAMES.issubset(plan_tools),
            f"plan_tools={sorted(plan_tools)} expected={sorted(REMOTE_READ_ANALYSIS_TOOL_NAMES)}",
        )
        self.assertFalse(REMOTE_WRITE_EXECUTION_TOOL_NAMES & ask_tools)
        self.assertFalse(REMOTE_WRITE_EXECUTION_TOOL_NAMES & plan_tools)
        self.assertFalse(REMOTE_WRITE_EXECUTION_TOOL_NAMES & agent_read_tools)
        self.assertTrue(REMOTE_WRITE_EXECUTION_TOOL_NAMES.issubset(agent_write_tools))
        self.assertFalse({"read_file", "glob", "grep", "bash"} & agent_write_tools)

    def test_remote_run_command_policy_blocks_shell_operators(self) -> None:
        tool = RemoteRunCommandTool(_remote_config(allow_write=True))

        self.assertIsNone(tool.validate_guarded_command("ls -la logs"))
        self.assertIn("denied operator", tool.validate_guarded_command("ls && pwd") or "")
        self.assertIn("denied operator", tool.validate_guarded_command("echo ok; pwd") or "")
        self.assertIn(
            "cannot pipe content into a shell",
            tool.validate_guarded_command("cat logs/app.log | sh") or "",
        )
        self.assertIn(
            "basePath",
            tool.validate_guarded_command("cat /etc/passwd") or "",
        )
        self.assertIn(
            "basePath",
            tool.validate_guarded_command("cat ../secrets.txt") or "",
        )
        self.assertIn(
            "basePath",
            tool.validate_guarded_command("cat /srv/app/../secrets.txt") or "",
        )
        self.assertIsNone(tool.validate_guarded_command("cat logs/app.log"))


if __name__ == "__main__":
    unittest.main()
