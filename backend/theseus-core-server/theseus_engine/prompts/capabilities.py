"""Capability-specific prompt sections and rendering helpers."""

from dataclasses import dataclass, field
from typing import Iterable, Optional

from theseus_engine.models.modes import (
    AgentMode,
    CoordinatorPhase,
    PlanPhase,
)
from theseus_engine.tools.tool_repair import (
    COMMON_CUSTOM_TOOL_SECURITY_RULES,
)


_TOOL_USE_CAPABILITY_PROMPT = """\
# Tool Use Capability
 - CRITICAL: You may ONLY call tools that appear in your function/tool schema for the current session. \
Do NOT invent, guess, or hallucinate tool names. If a tool does not appear in your schema, it does not exist.
 - Do NOT use Bash to run commands when a relevant dedicated tool is provided:
   - Read files: use read_file instead of cat/head/tail
   - Edit files: use edit_file instead of sed/awk
   - Create new files: use write_file instead of echo/heredoc
   - Search files: use glob instead of find/ls
   - Search content: use grep instead of grep/rg
   - Reserve Bash exclusively for system commands that require shell execution.
 - You can call multiple tools in a single response. Make independent calls in parallel for efficiency.
 - CRITICAL: NEVER use Markdown link syntax (e.g. `[label](url)`) in file paths, file names, or code content. \
When specifying a file path or writing code, use plain text only. \
Example — WRONG: `[sorter.py](http://sorter.py)`, CORRECT: `sorter.py`. \
Example — WRONG: `[x.is](http://x.is)_integer()`, CORRECT: `x.is_integer()`. \
This applies to ALL tool arguments (file_path, content, command, etc.) and to any Python/code you generate.\
"""

_RBAC_CAPABILITY_PROMPT = """\
# Theseus RBAC
 - Your available tools are filtered by the current user's permission level. \
You can only see and use tools that the user is authorized to access.
 - If a user requests an action that would require a tool not in your current schema, \
inform them that their permission level may not include that capability and suggest \
contacting their administrator for access elevation.
 - Do NOT mention specific permission levels or internal RBAC details to the user.\
"""

_VALIDATION_CAPABILITY_PROMPT = """\
# Theseus Validation Pipeline
 - Before every tool execution, the Theseus security pipeline (ExecutionValidator, \
QueryValidator) automatically scans your tool arguments for dangerous patterns.
 - If a tool call is BLOCKED by the validator, you will receive an error message starting \
with "[TheseusHook]". When this happens:
   (1) Read the validator's reason carefully.
   (2) Modify your tool arguments to remove the flagged pattern.
   (3) Retry with the corrected arguments.
   Do NOT retry with the exact same arguments — the validator will block it again.\
"""

_CODE_EDITING_SAFETY_PROMPT = """\
# Code Editing Safety Rules
 - Before editing a file, read the target file and confirm the exact location you will change.
 - Treat user constraints such as "do not change APP title" as invariants. Preserve those exact strings and include them in preserve_patterns when using file tools.
 - For comments, one-line edits, and small config changes, prefer edit_file with a unique old_str. Do not use write_file for existing files.
 - write_file is for new files by default. Existing-file overwrite requires allow_overwrite=true and a clear overwrite_reason because it replaces the whole file.
 - Keep edits narrowly scoped. Do not delete imports, classes, functions, or config keys unless the user explicitly requested that structural change.
 - After a file tool reports a safety rejection or rollback, explain the cause and retry with a smaller safer patch instead of claiming success.
 - Completion summaries for file edits must mention what changed and whether imports, declarations, config keys, and Python syntax were preserved.\
"""

_REMOTE_LOCAL_REPORT_PROMPT = """\
# Remote Workspace and Local Worktree Boundaries
 - When a Remote Workspace is selected, remote files/logs/resources must be inspected with remote_* tools such as remote_read_file, remote_glob, remote_grep, remote_tail_log, and remote_check_*.
 - Local tools such as read_file, glob, grep, write_file, and edit_file operate on the Core/local worktree, not on the Remote Workspace.
 - If the target is ambiguous, stop and clarify whether the user means the Remote Workspace or the Core/local worktree before calling a tool.
 - If the user asks to save a remote analysis/report locally, prefer local_write_report. It writes only report artifacts under reports/ or .theseus/reports/ with .md, .json, or .txt extensions.
 - Use local write_file/edit_file only for intentional Core/local worktree source changes or approved plan execution, never as a substitute for remote_write_file/remote_edit_file.\
"""

_CUSTOM_TOOL_RECOVERY_PROMPT = """\
# Custom Tool Recovery
 - If the user asks to list, search, or inspect available custom tools, call `tool_search` with the user's intent instead of answering from memory.
 - If the user asks for all custom tools, use a broad language-neutral query such as `custom tools`.
 - `tool_search` only makes already-registered callable tools available. It cannot directly call or register a Python file that failed to import.
 - Existing project custom tool artifacts are not normal workspace files. Do not use `read_file`, `edit_file`, or `write_file` on a custom tool artifact root such as `/opt/theseus/custom_tools` or the Core container custom tool mount.
 - To inspect an existing project custom tool source, use `custom_tool_read_source` with `project_id` plus `tool_name` or `module_name`.
 - To repair an existing project custom tool source, use `custom_tool_read_source` first, then `custom_tool_update_source` with the complete replacement source. The update tool stages, validates, sandbox-verifies, and only then replaces the active artifact.
 - Do not claim that `custom_tool_update_source` was attempted or succeeded unless the transcript contains that exact tool call result.
 - Treat a custom tool update as successful only when the tool result reports `status=updated` and metadata confirms `activationSource=custom_tool_update_source`, `lastMaintainedAt`, and `sandboxVerified=true`.
 - After a reported update success, verify by reading the tool again with `custom_tool_read_source`; only call it a runtime cache/registry problem if the metadata confirms the update but the next tool execution still uses old behavior.
 - If `create_tool` returns `create_tool requires an executing plan`, interpret it only as "tool creation did not run; an approved PLAN Executing phase is required." Do not describe it as successful creation, cache delay, or registration lag.
 - If a relevant custom tool is reported as unavailable, explain that the tool exists but is not callable until its import/dependency issue is resolved.
 - Prefer the extension's Custom Tools recovery flow for unavailable tools: install approved dependencies, retry load, then refresh the registry.
 - Do not call an unavailable custom tool by name until it appears in your current tool schema.\
"""

_WEB_RESEARCH_CAPABILITY_PROMPT = """\
# Web Research Capability
 - When writing or modifying tools/scripts that interact with external services \
(e.g., web scrapers, API clients), verify the current URL structure, DOM elements, \
or API contract using available web research tools unless the specification is \
already present in local files or the user has provided authoritative documentation.
 - For tasks requiring multiple independent web sources, prefer `deep_research` when \
it is available because it handles search, scraping, and parsing in a single turn.\
"""

_GENERATED_CUSTOM_TOOL_SECURITY_RULES = """\
Generated Theseus custom tool security rules:
 - Do not import or call subprocess, os.system, os.popen, shutil, socket, ctypes, \
multiprocessing, signal, pty, resource, tempfile, webbrowser, pickle, or shelve.
 - Do not execute shell commands or arbitrary local programs from generated custom tools.
 - Do not read or write arbitrary local files unless the approved plan explicitly names \
safe read-only paths.
 - If a generated custom tool must use another active Theseus tool, call it only with \
`await context.call_tool("tool_name", {...})`. Do not read `context.metadata["tool_registry"]` \
directly or import another tool module by file path.
 - For system metrics, prefer psutil and read-only /proc or /sys data. Do not call \
nvidia-smi directly from a generated custom tool.
 - If a core requirement depends on a prohibited command or module, expose the limitation \
and propose a safe alternative instead of silently removing that capability.\
"""

_CREATE_TOOL_CAPABILITY_PROMPT = """\
# create_tool Capability
 - Tool creation (`create_tool`) is ONLY available in Plan mode's Executing phase. Do not attempt it in Agent, Ask, Drafting, Review, or Verifying mode.
 - `tool_search` may show `create_tool` as a search match outside Plan Executing, but it is not callable there. If it is marked "Not injectable", explain the required mode instead of calling it.
 - When using `create_tool`, you MUST produce a complete, self-contained Python module that:
   (1) imports BaseTool, ToolExecutionContext, ToolResult from theseus_engine.tools.core.base_tools
   (2) imports BaseModel, Field from pydantic
   (3) defines an input model inheriting BaseModel — name it `<ToolClassWithoutTool>Input` \
(preferred, e.g., WeatherFetcherInput for WeatherFetcherTool) or `<ToolClassName>Input`; \
helper/output BaseModel classes are allowed when useful
   (4) defines a tool class inheriting BaseTool with name, description, input_model, permission_level
   (5) implements async execute(self, arguments: <InputModel>, context: ToolExecutionContext) -> ToolResult
   (6) returns ToolResult(output=...) on success, ToolResult(output=..., is_error=True) on failure
 - IMPORTANT: Do NOT use ToolResult.from_error() or ToolResult(status=..., data=...) — they don't exist.
 - When a tool needs threshold-based detail analysis, first collect summary metrics inside \
the current tool, then call active detail tools with `await context.call_tool("cpu_monitor", {"top_n": 10})` \
or the matching tool schema. Handle `is_error=True` results in the final report.
 - Nested tool calls are for bounded diagnostic composition. Do not call the same tool with \
the same arguments repeatedly, and do not use nested calls for write/edit/bash/reboot-style actions.
 - Generated custom tools must follow the shared Theseus security rules below.
 - You CANNOT create a tool and call it in the SAME turn. Call `create_tool`, wait for \
the success result, and ONLY THEN call the newly created tool in your next response.\
""" + "\n" + COMMON_CUSTOM_TOOL_SECURITY_RULES


@dataclass(frozen=True)
class PromptCapabilities:
    """현재 prompt turn에 주입할 runtime capability 정보."""

    available_tools: frozenset[str] = field(default_factory=frozenset)
    runtime_reminders: tuple[str, ...] = ()

    def has_any_tool(self) -> bool:
        return bool(self.available_tools)

    def has_tool(self, name: str) -> bool:
        return name in self.available_tools


_WEB_RESEARCH_TOOL_NAMES = frozenset({"web_search", "web_fetch", "deep_research"})
_REMOTE_CONTEXT_TOOL_NAMES = frozenset(
    {
        "remote_read_file",
        "remote_glob",
        "remote_grep",
        "remote_tail_log",
        "remote_check_cpu",
        "remote_check_memory",
        "remote_check_disk",
        "remote_write_file",
        "remote_edit_file",
        "remote_run_command",
        "local_write_report",
    }
)
_AGENT_DEFAULT_TOOL_NAMES = frozenset(
    {
        "bash",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "web_search",
        "web_fetch",
        "deep_research",
        "tool_search",
        "search_knowledge_base",
        "ingest_document",
    }
)
_PLAN_DRAFTING_DEFAULT_TOOL_NAMES = frozenset(
    {"bash", "read_file", "glob", "grep", "web_search", "web_fetch", "deep_research"}
)
_PLAN_REVIEW_DEFAULT_TOOL_NAMES = frozenset({"read_file", "glob", "grep"})
_PLAN_EXECUTING_DEFAULT_TOOL_NAMES = _AGENT_DEFAULT_TOOL_NAMES | frozenset({"create_tool"})
_PLAN_VERIFYING_DEFAULT_TOOL_NAMES = _AGENT_DEFAULT_TOOL_NAMES
_COORDINATOR_DEFAULT_TOOL_NAMES = frozenset(
    {"agent", "task_output", "read_file", "glob", "grep", "bash"}
)


def _normalize_available_tools(
    available_tools: Iterable[str] | None,
) -> frozenset[str] | None:
    """Tool schema에서 전달된 도구 이름을 prompt capability 집합으로 정규화합니다."""
    if available_tools is None:
        return None
    normalized: set[str] = set()
    for name in available_tools:
        value = str(name).strip()
        if value:
            normalized.add(value)
    return frozenset(normalized)


def _default_tool_names_for_mode(
    mode: AgentMode,
    plan_phase: Optional[PlanPhase],
    coordinator_phase: Optional[CoordinatorPhase],
) -> frozenset[str]:
    """레거시 호출자가 tool schema를 넘기지 않는 경우의 보수적 기본값."""
    if mode == AgentMode.ASK:
        return frozenset()
    if mode == AgentMode.AGENT:
        return _AGENT_DEFAULT_TOOL_NAMES
    if mode == AgentMode.PLAN:
        if plan_phase == PlanPhase.DRAFTING:
            return _PLAN_DRAFTING_DEFAULT_TOOL_NAMES
        if plan_phase == PlanPhase.WAIT_FOR_REVIEW:
            return _PLAN_REVIEW_DEFAULT_TOOL_NAMES
        if plan_phase == PlanPhase.EXECUTING:
            return _PLAN_EXECUTING_DEFAULT_TOOL_NAMES
        if plan_phase == PlanPhase.VERIFYING:
            return _PLAN_VERIFYING_DEFAULT_TOOL_NAMES
        return _PLAN_DRAFTING_DEFAULT_TOOL_NAMES
    if mode == AgentMode.COORDINATOR:
        return _COORDINATOR_DEFAULT_TOOL_NAMES
    return frozenset()


def _build_prompt_capabilities(
    *,
    mode: AgentMode,
    plan_phase: Optional[PlanPhase],
    coordinator_phase: Optional[CoordinatorPhase],
    available_tools: Iterable[str] | None,
    runtime_reminders: Iterable[str] | None,
) -> PromptCapabilities:
    tools = _normalize_available_tools(available_tools)
    if tools is None:
        tools = _default_tool_names_for_mode(mode, plan_phase, coordinator_phase)

    reminders = tuple(
        value
        for value in (str(item).strip() for item in (runtime_reminders or ()))
        if value
    )
    return PromptCapabilities(available_tools=tools, runtime_reminders=reminders)


def _render_capability_sections(capabilities: PromptCapabilities) -> str:
    sections: list[str] = []
    if capabilities.has_any_tool():
        sections.extend(
            [
                _TOOL_USE_CAPABILITY_PROMPT,
                _RBAC_CAPABILITY_PROMPT,
                _VALIDATION_CAPABILITY_PROMPT,
            ]
        )
    if capabilities.available_tools & {"write_file", "edit_file", "remote_write_file", "remote_edit_file"}:
        sections.append(_CODE_EDITING_SAFETY_PROMPT)
    if capabilities.available_tools & _REMOTE_CONTEXT_TOOL_NAMES:
        sections.append(_REMOTE_LOCAL_REPORT_PROMPT)
    if capabilities.has_tool("tool_search"):
        sections.append(_CUSTOM_TOOL_RECOVERY_PROMPT)
    if capabilities.available_tools & _WEB_RESEARCH_TOOL_NAMES:
        sections.append(_WEB_RESEARCH_CAPABILITY_PROMPT)
    if capabilities.has_tool("create_tool"):
        sections.append(_CREATE_TOOL_CAPABILITY_PROMPT)
    return "\n\n".join(sections)


def _render_runtime_reminders(reminders: tuple[str, ...]) -> str:
    if not reminders:
        return ""
    lines = ["# Runtime Reminders"]
    lines.extend(f" - {item}" for item in reminders)
    return "\n".join(lines)


TOOL_USE_CAPABILITY_PROMPT = _TOOL_USE_CAPABILITY_PROMPT
RBAC_PERMISSION_PROMPT = _RBAC_CAPABILITY_PROMPT
VALIDATION_CAPABILITY_PROMPT = _VALIDATION_CAPABILITY_PROMPT
CODE_EDITING_SAFETY_PROMPT = _CODE_EDITING_SAFETY_PROMPT
WEB_CAPABILITY_PROMPT = _WEB_RESEARCH_CAPABILITY_PROMPT
GENERATED_CUSTOM_TOOL_SECURITY_RULES = _GENERATED_CUSTOM_TOOL_SECURITY_RULES
CREATE_TOOL_CAPABILITY_PROMPT = _CREATE_TOOL_CAPABILITY_PROMPT
CUSTOM_TOOL_RECOVERY_PROMPT = _CUSTOM_TOOL_RECOVERY_PROMPT
REMOTE_LOCAL_REPORT_PROMPT = _REMOTE_LOCAL_REPORT_PROMPT

normalize_available_tools = _normalize_available_tools
default_tool_names_for_mode = _default_tool_names_for_mode
build_prompt_capabilities = _build_prompt_capabilities
render_capability_sections = _render_capability_sections
render_runtime_reminders = _render_runtime_reminders

__all__ = [
    "PromptCapabilities",
    "TOOL_USE_CAPABILITY_PROMPT",
    "RBAC_PERMISSION_PROMPT",
    "VALIDATION_CAPABILITY_PROMPT",
    "CODE_EDITING_SAFETY_PROMPT",
    "WEB_CAPABILITY_PROMPT",
    "GENERATED_CUSTOM_TOOL_SECURITY_RULES",
    "CREATE_TOOL_CAPABILITY_PROMPT",
    "CUSTOM_TOOL_RECOVERY_PROMPT",
    "REMOTE_LOCAL_REPORT_PROMPT",
    "normalize_available_tools",
    "default_tool_names_for_mode",
    "build_prompt_capabilities",
    "render_capability_sections",
    "render_runtime_reminders",
]
