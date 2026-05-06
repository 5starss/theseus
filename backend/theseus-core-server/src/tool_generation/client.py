import logging

import httpx
from pydantic import ValidationError

from src.auth.client import internal_api_headers, unwrap_api_response
from src.config import settings
from src.tool_generation.schemas import ToolDraftPayload

logger = logging.getLogger(__name__)


class ToolDraftClientError(Exception):
    """Base error for Tool draft lookups."""


class ToolDraftNotFoundError(ToolDraftClientError):
    """Raised when the API server cannot find the Tool draft."""


class ToolDraftInvalidResponseError(ToolDraftClientError):
    """Raised when the API server returns an invalid draft payload."""


class ToolDraftBackendUnavailableError(ToolDraftClientError):
    """Raised when the API server cannot serve Tool draft lookups."""


class ToolDraftClient:
    def __init__(self) -> None:
        self.url_template = settings.SPRING_BOOT_INTERNAL_TOOL_DRAFT_URL
        self.timeout = settings.INTERNAL_API_TIMEOUT_SECONDS

    async def fetch_tool_draft(self, tool_id: int) -> ToolDraftPayload:
        url = self.url_template.format(tool_id=tool_id)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=internal_api_headers(),
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                logger.error("Failed to connect to Tool draft API: %s", exc)
                raise ToolDraftBackendUnavailableError from exc

        if response.status_code == 200:
            try:
                return ToolDraftPayload.model_validate(unwrap_api_response(response.json()))
            except (TypeError, ValueError, ValidationError) as exc:
                logger.error("Invalid Tool draft response schema: %s", exc)
                raise ToolDraftInvalidResponseError from exc

        if response.status_code == 404:
            raise ToolDraftNotFoundError

        logger.error("Tool draft API error: %s - %s", response.status_code, response.text)
        raise ToolDraftBackendUnavailableError


tool_draft_client = ToolDraftClient()
