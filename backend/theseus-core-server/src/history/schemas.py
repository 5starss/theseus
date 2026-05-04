from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HistoryMessageRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: int = Field(alias="messageId")
    chat_session_id: int = Field(alias="chatSessionId")
    tool_id: int | None = Field(default=None, alias="toolId")
    message_order: int = Field(alias="messageOrder")
    sender_type: Literal["USER", "ASSISTANT", "SYSTEM"] = Field(alias="senderType")
    message_type: str | None = Field(default=None, alias="messageType")
    content_type: str | None = Field(default=None, alias="contentType")
    content: str
    created_at: datetime | None = Field(default=None, alias="createdAt")


HistorySenderType = Literal["USER", "ASSISTANT", "SYSTEM"]


class HistoryMessageCreateRequest(BaseModel):
    project_id: int
    chat_session_id: int
    sender_type: HistorySenderType
    content: str
    tool_id: int | None = None
    message_type: str | None = "CHAT"
    content_type: str | None = "TEXT"
