import httpx
from pydantic import TypeAdapter, ValidationError

from src.auth.client import internal_api_headers, unwrap_api_response
from src.auth.schemas import SessionContext
from src.config import settings
from src.history.schemas import HistoryMessageCreateRequest, HistoryMessageRecord


class HistoryClientError(Exception):
    """Base error for chat history integration failures."""


class HistoryClient:
    def __init__(self) -> None:
        self.base_url = settings.SPRING_BOOT_INTERNAL_URL.rstrip("/")
        self.history_save_url = settings.SPRING_BOOT_INTERNAL_HISTORY_MESSAGES_URL
        self.timeout = settings.INTERNAL_API_TIMEOUT_SECONDS
        self._message_list_adapter = TypeAdapter(list[HistoryMessageRecord])

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _message_list_url(self, project_id: str, chat_session_id: int) -> str:
        return (
            f"{self.base_url}/api/v1/projects/{project_id}/sessions/"
            f"{chat_session_id}/messages"
        )

    async def fetch_messages(
        self,
        session: SessionContext,
        chat_session_id: int,
    ) -> list[HistoryMessageRecord]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self._message_list_url(session.project_id, chat_session_id),
                    headers=self._auth_headers(session.token),
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                raise HistoryClientError("Failed to fetch history messages") from exc

        if response.status_code != 200:
            raise HistoryClientError(
                f"History fetch failed with status {response.status_code}"
            )

        try:
            payload = response.json()
            return self._message_list_adapter.validate_python(unwrap_api_response(payload) or [])
        except (ValueError, ValidationError) as exc:
            raise HistoryClientError("Invalid history payload received") from exc

    async def save_message(
        self,
        session: SessionContext,
        request: HistoryMessageCreateRequest,
    ) -> None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.history_save_url,
                    headers=internal_api_headers(),
                    json={
                        "userId": session.user_id,
                        "projectId": request.project_id,
                        "chatSessionId": request.chat_session_id,
                        "senderType": request.sender_type,
                        "content": request.content,
                        "toolId": request.tool_id,
                        "messageType": request.message_type,
                        "contentType": request.content_type,
                    },
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                raise HistoryClientError("Failed to save history message") from exc

        if response.status_code not in (200, 201):
            raise HistoryClientError(f"History save failed with status {response.status_code}")


history_client = HistoryClient()
