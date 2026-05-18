"""Theseus Core Tools — 모든 내장 도구의 중앙 레지스트리.

이 패키지에서 모든 핵심 도구 클래스를 임포트할 수 있습니다.
engine_builder.py는 이 __init__만 임포트하면 됩니다.

Usage:
    from theseus_engine.tools.core import ALL_CORE_TOOLS
    for tool_cls in ALL_CORE_TOOLS:
        registry.register(tool_cls())
"""

# ── Base / Test Tools ────────────────────────────────────────────
from theseus_engine.tools.core.base_tools import DummyTool, SystemRebootTool

# ── Meta Tooling (create, validate, load) ────────────────────────
from theseus_engine.tools.core.tool_factory import (
    ToolCreatorTool,
    ToolValidator,
    build_filtered_registry,
    load_custom_tools,
    load_custom_tools_for_project,
    scan_custom_tool_inventory,
)

# ── File Operations ──────────────────────────────────────────────
from theseus_engine.tools.core.file_read_tool import ReadFileTool
from theseus_engine.tools.core.file_write_tool import WriteFileTool
from theseus_engine.tools.core.file_edit_tool import EditFileTool
from theseus_engine.tools.core.local_report_tool import LocalWriteReportTool
from theseus_engine.tools.core.glob_tool import GlobTool
from theseus_engine.tools.core.grep_tool import GrepTool

# ── Web Operations ───────────────────────────────────────────────
from theseus_engine.tools.core.web_fetch_tool import WebFetchTool
from theseus_engine.tools.core.web_search_tool import WebSearchTool
from theseus_engine.tools.core.deep_research_tool import DeepResearchTool

# ── System & Shell ───────────────────────────────────────────────
from theseus_engine.tools.core.bash_tool import BashTool

# ── Code Intelligence ────────────────────────────────────────────
from theseus_engine.tools.core.lsp_tool import LspTool

# ── Sub-Agent Delegation ────────────────────────────────────────
from theseus_engine.tools.core.agent_tool import AgentTool

# ── Background Tasks ────────────────────────────────────────────
from theseus_engine.tools.core.task_create_tool import TaskCreateTool
from theseus_engine.tools.core.task_list_tool import TaskListTool
from theseus_engine.tools.core.task_output_tool import TaskOutputTool
from theseus_engine.tools.core.task_stop_tool import TaskStopTool
from theseus_engine.tools.core.task_get_tool import TaskGetTool

# ── MCP (Model Context Protocol) ────────────────────────────────
from theseus_engine.tools.core.mcp_tools import (
    ListMcpResourcesTool,
    ReadMcpResourceTool,
)

# ── Skills (Knowledge Reuse) ───────────────────────────────────
from theseus_engine.tools.core.skill_tools import (
    SkillReadTool,
    SkillSaveTool,
    SkillListTool,
)

# ── Project & Sandbox Management ───────────────────────────────
from theseus_engine.tools.core.worktree_tools import (
    EnterWorktreeTool,
    ExitWorktreeTool,
)
from theseus_engine.tools.core.brief_tool import BriefTool

# ── Tool Discovery (RAG 폴백) ─────────────────────────────────────
from theseus_engine.tools.core.tool_search_tool import ToolSearchTool

# ── Agent Memory (3-scope) ───────────────────────────────────────
from theseus_engine.tools.core.memory_tools import (
    MemoryWriteTool,
    MemoryReadTool,
    MemoryListTool,
)

# ── Interactive & Knowledge ──────────────────────────────────────
from theseus_engine.tools.core.interactive_tools import AskUserTool
from theseus_engine.tools.core.knowledge_tools import (
    SearchKnowledgeBaseTool,
    IngestDocumentTool,
)
from theseus_engine.tools.core.todo_write_tool import TodoWriteTool


# ── 전체 도구 목록 (engine_builder에서 순회 등록용) ────────────
ALL_CORE_TOOLS = [
    # Base
    DummyTool,
    SystemRebootTool,
    # Meta
    ToolCreatorTool,
    ToolSearchTool,
    # File
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    LocalWriteReportTool,
    GlobTool,
    GrepTool,
    # Web
    WebFetchTool,
    WebSearchTool,
    DeepResearchTool,
    # Shell
    BashTool,
    # Code Intelligence
    LspTool,
    # Sub-Agent
    AgentTool,
    # Tasks
    TaskCreateTool,
    TaskListTool,
    TaskOutputTool,
    TaskStopTool,
    TaskGetTool,
    # MCP
    ListMcpResourcesTool,
    ReadMcpResourceTool,
    # Skills
    SkillReadTool,
    SkillSaveTool,
    SkillListTool,
    # Project & Sandbox
    EnterWorktreeTool,
    ExitWorktreeTool,
    BriefTool,
    # Interactive
    AskUserTool,
    # Knowledge
    SearchKnowledgeBaseTool,
    IngestDocumentTool,
    # Project management
    TodoWriteTool,
    # Memory
    MemoryWriteTool,
    MemoryReadTool,
    MemoryListTool,
]
