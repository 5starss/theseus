"""Briefing and summarization tool for Theseus."""

from __future__ import annotations

import logging
from typing import Optional
from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)


class BriefInput(BaseModel):
    """Arguments for summarization."""

    text: str = Field(description="The long text, conversation, or state to summarize")
    max_tokens: Optional[int] = Field(default=300, description="Target length in words/tokens")


BriefInput.model_rebuild()


class BriefTool(BaseTool):
    """Summarize long text or project state to save context space."""

    name = "brief"
    description = (
        "Compress a long piece of text, conversation history, or project state "
        "into a concise summary. Use this to maintain memory efficiency."
    )
    input_model = BriefInput
    permission_level = 1

    async def execute(
        self, arguments: BriefInput, context: ToolExecutionContext
    ) -> ToolResult:
        text = arguments.text.strip()
        if not text:
            return ToolResult(output="(No content to summarize)")

        # TODO: Future enhancement - Use LLM to summarize if api_client is available in context
        # For now, implement smart structural compression
        
        lines = text.splitlines()
        if len(lines) <= 20:
            return ToolResult(output=text)
        
        # Keep the first 10 and last 10 lines, with a summary gap
        summary = (
            f"[Summary of {len(lines)} lines, structural compression applied]\n"
            + "\n".join(lines[:10])
            + "\n\n... (omitted) ...\n\n"
            + "\n".join(lines[-10:])
        )
        
        return ToolResult(
            output=(
                f"📋 Summary (compressed):\n\n"
                f"{summary}\n\n"
                f"Refer to the conversation history for full content."
            )
        )
