"""다국어 LLM 기반 승인 의도 분류기."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

_CLASSIFIER_PROMPT = (
    "You are a strict multilingual intent classifier. "
    "Determine if the user's short message expresses UNCONDITIONAL APPROVAL to proceed with a plan. "
    "It may be in any language (e.g. 'Yes', 'ㅇㅋ', 'Sí', 'Oui', 'はい', 'Go ahead'). "
    "If there are ANY conditions, modifications, or questions (e.g. 'Yes, but...', 'Fix task-1 first'), it is NOT an approval. "
    "Reply with EXACTLY one word: YES or NO."
)


async def llm_is_approval(text: str, client: "TheseusLLMClient") -> bool:
    """다국어를 지원하는 LLM 기반 승인 의도 판별기.

    100자 초과 입력은 즉시 False(피드백) 처리하여 LLM 호출을 생략합니다.
    나머지는 LLM에 위임하여 언어·뉘앙스에 관계없이 의도를 정확히 분류합니다.
    LLM 장애 시에는 보수적으로 False를 반환합니다.
    """
    from openharness.api.client import ApiMessageRequest, ApiTextDeltaEvent
    from openharness.engine.messages import ConversationMessage, TextBlock

    t = text.strip()
    if len(t) > 100:
        return False

    try:
        request = ApiMessageRequest(
            model=client.model_name.split("/", 1)[-1] if "/" in client.model_name else client.model_name,
            messages=[ConversationMessage(
                role="user",
                content=[TextBlock(text=f"Message: '{t}'")],
            )],
            system_prompt=_CLASSIFIER_PROMPT,
            max_tokens=5,
        )
        result = ""
        async for event in client.stream_message(request):
            if isinstance(event, ApiTextDeltaEvent):
                result += event.text
        return "YES" in result.strip().upper()
    except Exception as e:
        print(f"[!] Intent classifier error: {e}")
        return False
