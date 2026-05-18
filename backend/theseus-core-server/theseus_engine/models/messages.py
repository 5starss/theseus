"""Theseus-native conversation message types.

외부 에이전트 프레임워크 의존 없이 동일한 Pydantic 구조를 제공합니다.
QueryEngine / LLM Client 전환 시 이 모듈만 변경하면 됩니다.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ── Content Blocks ────────────────────────────────────────────


class TextBlock(BaseModel):
    """Plain text content."""
    type: Literal["text"] = "text"
    text: str


class ImageBlock(BaseModel):
    """Image content encoded inline for multimodal providers."""
    type: Literal["image"] = "image"
    media_type: str
    data: str
    source_path: str = ""

    @classmethod
    def from_path(cls, path: str | Path) -> "ImageBlock":
        resolved = Path(path).expanduser().resolve()
        media_type, _ = mimetypes.guess_type(str(resolved))
        if not media_type or not media_type.startswith("image/"):
            raise ValueError(f"Unsupported image attachment: {resolved}")
        payload = base64.b64encode(resolved.read_bytes()).decode("ascii")
        return cls(media_type=media_type, data=payload, source_path=str(resolved))


class ToolUseBlock(BaseModel):
    """A request from the model to execute a named tool."""
    type: Literal["tool_use"] = "tool_use"
    id: str = Field(default_factory=lambda: f"toolu_{uuid4().hex}")
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """Tool result content sent back to the model."""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False

    @field_validator("content", mode="before")
    @classmethod
    def _stringify_content(cls, value: Any) -> str:
        return stringify_message_content(value)


ContentBlock = Annotated[
    TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]


def stringify_message_content(value: Any) -> str:
    """Normalize message-bound content into provider-safe text."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


# ── ConversationMessage ───────────────────────────────────────


class ConversationMessage(BaseModel):
    """A single assistant or user message."""

    role: Literal["user", "assistant"]
    content: list[ContentBlock] = Field(default_factory=list)

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        return value

    @classmethod
    def from_user_text(cls, text: str) -> "ConversationMessage":
        return cls(role="user", content=[TextBlock(text=text)])

    @classmethod
    def from_user_content(cls, content: list[ContentBlock]) -> "ConversationMessage":
        return cls(role="user", content=list(content))

    @property
    def text(self) -> str:
        return "".join(
            block.text for block in self.content if isinstance(block, TextBlock)
        )

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        return [block for block in self.content if isinstance(block, ToolUseBlock)]

    def to_api_param(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": [serialize_content_block(block) for block in self.content],
        }

    def is_effectively_empty(self) -> bool:
        if self.content:
            for block in self.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    return False
                if isinstance(block, (ImageBlock, ToolUseBlock, ToolResultBlock)):
                    return False
        return True


# ── Helpers ───────────────────────────────────────────────────


def serialize_content_block(block: ContentBlock) -> dict[str, Any]:
    """Convert a local content block into the provider wire format."""
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ImageBlock):
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": block.media_type,
                "data": block.data,
            },
        }
    if isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {
        "type": "tool_result",
        "tool_use_id": block.tool_use_id,
        "content": block.content,
        "is_error": block.is_error,
    }


def assistant_message_from_api(raw_message: Any) -> ConversationMessage:
    """Convert an Anthropic SDK message object into a ConversationMessage."""
    content: list[ContentBlock] = []
    for raw_block in getattr(raw_message, "content", []):
        block_type = getattr(raw_block, "type", None)
        if block_type == "text":
            content.append(TextBlock(text=getattr(raw_block, "text", "")))
        elif block_type == "tool_use":
            content.append(ToolUseBlock(
                id=getattr(raw_block, "id", f"toolu_{uuid4().hex}"),
                name=getattr(raw_block, "name", ""),
                input=dict(getattr(raw_block, "input", {}) or {}),
            ))
    return ConversationMessage(role="assistant", content=content)


def sanitize_conversation_messages(
    messages: list[ConversationMessage],
) -> list[ConversationMessage]:
    """Normalize conversation history into a provider-safe sequence.

    Drops legacy empty assistant messages and trims malformed trailing
    tool turns (assistant tool_use without matching user tool_result).
    """
    sanitized: list[ConversationMessage] = []
    pending_tool_use_ids: set[str] = set()
    pending_tool_use_index: int | None = None

    for message in messages:
        if message.role == "assistant" and message.is_effectively_empty():
            continue

        tool_uses = message.tool_uses if message.role == "assistant" else []
        tool_results = (
            [b for b in message.content if isinstance(b, ToolResultBlock)]
            if message.role == "user"
            else []
        )

        matched_pending_tool_results = False
        if pending_tool_use_ids:
            result_ids = {b.tool_use_id for b in tool_results}
            if message.role != "user" or not pending_tool_use_ids.issubset(result_ids):
                if (
                    pending_tool_use_index is not None
                    and pending_tool_use_index < len(sanitized)
                ):
                    sanitized.pop(pending_tool_use_index)
                pending_tool_use_ids = set()
                pending_tool_use_index = None
            else:
                matched_pending_tool_results = True
                pending_tool_use_ids = set()
                pending_tool_use_index = None

        if message.role == "user" and tool_results and not matched_pending_tool_results:
            content = [b for b in message.content if not isinstance(b, ToolResultBlock)]
            if not content:
                continue
            message = ConversationMessage(role="user", content=content)

        sanitized.append(message)

        if tool_uses:
            pending_tool_use_ids = {b.id for b in tool_uses}
            pending_tool_use_index = len(sanitized) - 1

    if (
        pending_tool_use_ids
        and pending_tool_use_index is not None
        and pending_tool_use_index < len(sanitized)
    ):
        sanitized.pop(pending_tool_use_index)

    return sanitized
