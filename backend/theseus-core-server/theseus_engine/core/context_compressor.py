"""Context Compressor

대화 메시지가 임계값을 초과하면 오래된 메시지를 LLM 요약으로 압축합니다.

설계 원칙:
- 최근 N개 메시지는 항상 원본 보존 (단기 기억)
- 그 이전 메시지들은 단일 요약 메시지로 교체 (장기 기억 압축)
- 요약 생성에 LLM 클라이언트가 없으면 구조적 압축으로 fallback
"""

from __future__ import annotations

import logging
from typing import List, Optional

log = logging.getLogger(__name__)

# 기본 설정값
DEFAULT_MAX_MESSAGES = 30       # 이 수를 초과하면 압축 트리거
DEFAULT_KEEP_RECENT = 10        # 최근 N개는 원본 유지
DEFAULT_SUMMARY_ROLE = "user"   # 요약 삽입 역할 (일부 LLM은 system 거부)


def _structural_summary(messages: list) -> str:
    """LLM 없이 구조적으로 메시지를 요약합니다 (fallback)."""
    lines = []
    for m in messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "?")
        # ConversationMessage 또는 dict 모두 처리
        if hasattr(m, "text"):
            content_preview = (m.text or "")[:80]
        elif isinstance(m, dict):
            content = m.get("content", "")
            content_preview = (content if isinstance(content, str) else str(content))[:80]
        else:
            content_preview = str(m)[:80]
        lines.append(f"[{role}] {content_preview}{'...' if len(content_preview) == 80 else ''}")
    return "\n".join(lines)


def needs_compression(messages: list, max_messages: int = DEFAULT_MAX_MESSAGES) -> bool:
    """메시지 수가 임계값을 초과하는지 확인합니다."""
    return len(messages) > max_messages


async def compress_messages(
    messages: list,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    api_client=None,
    model: Optional[str] = None,
) -> list:
    """오래된 메시지를 요약으로 대체한 새 메시지 리스트를 반환합니다.

    원본 리스트를 변경하지 않고 새 리스트를 반환합니다.

    Args:
        messages: 현재 전체 메시지 리스트.
        keep_recent: 원본 유지할 최근 메시지 수.
        api_client: LLM 클라이언트 (있으면 LLM 요약, 없으면 구조적 압축).
        model: 요약에 사용할 모델명.

    Returns:
        압축된 새 메시지 리스트.
    """
    if len(messages) <= keep_recent:
        return list(messages)

    old_msgs = messages[:-keep_recent]
    recent_msgs = messages[-keep_recent:]

    summary_text = await _build_summary(old_msgs, api_client, model)

    # 요약을 단일 user 메시지로 삽입
    summary_entry = _make_summary_message(summary_text, messages)

    compressed = [summary_entry] + list(recent_msgs)
    log.info(
        "[ContextCompressor] %d개 → %d개 메시지로 압축 (최근 %d개 원본 유지)",
        len(messages),
        len(compressed),
        keep_recent,
    )
    return compressed


async def _build_summary(old_msgs: list, api_client, model: Optional[str]) -> str:
    """이전 메시지들의 요약 텍스트를 생성합니다."""
    raw_text = _structural_summary(old_msgs)

    if api_client is None:
        return f"[이전 대화 요약 — {len(old_msgs)}개 메시지]\n{raw_text}"

    # LLM 요약 시도 (이미 async 컨텍스트이므로 직접 await)
    try:
        prompt = (
            "다음은 AI 에이전트와의 이전 대화 기록입니다. "
            "핵심 결정 사항, 완료된 작업, 중요한 파일/도구 사용 내역을 "
            "간결하게 3~5문장으로 요약해주세요.\n\n"
            f"{raw_text}"
        )
        # TheseusAnthropicClient 등은 chat_completion() 미지원 — stream_message() 사용
        if not hasattr(api_client, "chat_completion"):
            raise AttributeError(
                f"{type(api_client).__name__} does not support chat_completion(). "
                "Falling back to structural summary."
            )
        response = await api_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=400,
        )
        return response.choices[0].message.content or raw_text
    except Exception as e:
        log.debug("[ContextCompressor] LLM 요약 실패, 구조적 요약 사용: %s", e)
        return f"[이전 대화 요약 — {len(old_msgs)}개 메시지]\n{raw_text}"


def _make_summary_message(summary_text: str, original_messages: list):
    """메시지 리스트의 형식(ConversationMessage or dict)에 맞는 요약 엔트리를 생성합니다."""
    first = original_messages[0] if original_messages else None

    # ConversationMessage 형식 감지
    if first is not None and hasattr(first, "role"):
        from theseus_engine.models.messages import ConversationMessage, TextBlock
        return ConversationMessage(
            role=DEFAULT_SUMMARY_ROLE,
            content=[TextBlock(text=summary_text)],
        )

    # dict fallback
    return {"role": DEFAULT_SUMMARY_ROLE, "content": summary_text}


async def maybe_compress(
    messages: list,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    api_client=None,
    model: Optional[str] = None,
) -> tuple[list, bool]:
    """필요한 경우에만 압축을 수행합니다.

    Args:
        messages: 현재 전체 메시지 리스트.
        max_messages: 압축 트리거 임계값.
        keep_recent: 원본 유지할 최근 메시지 수.
        api_client: LLM 클라이언트 (선택).
        model: 요약 모델명 (선택).

    Returns:
        (새 메시지 리스트, 압축 여부) 튜플.
    """
    if not needs_compression(messages, max_messages):
        return list(messages), False

    compressed = await compress_messages(messages, keep_recent, api_client, model)
    return compressed, True
