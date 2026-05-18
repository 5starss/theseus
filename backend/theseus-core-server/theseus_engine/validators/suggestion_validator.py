"""Suggestion Validator: LLM 기반 코드 품질 개선 제안기.

에이전트가 create_tool을 통해 생성한 코드를 대상으로,
더 Pythonic하고 성능이 좋은 방향으로 리팩토링할 수
있는지 LLM에게 코드 리뷰를 요청합니다.

이 검증기는 코드 생성 시점(create_tool 내부)에 동작하며,
실행을 차단(block)하지 않고 '제안(suggestion)'만 반환합니다.
"""

from __future__ import annotations

import logging
from typing import Tuple

log = logging.getLogger(__name__)

# 코드 리뷰 시스템 프롬프트 (언어 중립)
_REVIEW_SYSTEM_PROMPT = (
    "You are a senior Python code reviewer. "
    "Review the following code and provide concise, "
    "actionable suggestions to improve:\n"
    "1. Pythonic idioms and best practices\n"
    "2. Performance optimizations\n"
    "3. Error handling improvements\n"
    "4. Type hint completeness\n"
    "Respond in the language requested by the caller or surrounding task context. "
    "If the code is already excellent, respond with a short no-issues sentence "
    "in that same language."
)


class SuggestionValidator:
    """생성된 코드의 품질을 LLM에게 리뷰 받는 제안기.

    실행을 차단하지 않으며, 개선 제안만 텍스트로 반환합니다.
    """

    @classmethod
    def review(cls, code: str) -> Tuple[bool, str]:
        """코드에 대한 품질 리뷰를 수행합니다.

        Args:
            code: 리뷰 대상 파이썬 코드 문자열.

        Returns:
            (True, 리뷰 결과 텍스트) 튜플.
            이 검증기는 항상 True를 반환합니다 (차단 없음).

        Note:
            현재 LLM 호출은 Stub으로 구현되어 있습니다.
            향후 TheseusLLMClient와 연동하여 실제 리뷰를
            수행할 예정입니다.
        """
        log.warning(
            "[Suggestion] 코드 품질 리뷰 요청 (코드 길이: %d자) — "
            "현재 LLM 검증기가 미구현(Stub) 상태입니다. "
            "TheseusLLMClient 연동 전까지 실제 리뷰가 수행되지 않습니다.",
            len(code),
        )

        # TODO: TheseusLLMClient를 통해 실제 LLM 호출 구현
        # request = ApiMessageRequest(
        #     model=<lightweight_model>,
        #     messages=[
        #         ConversationMessage.from_user_text(code)
        #     ],
        #     system_prompt=_REVIEW_SYSTEM_PROMPT,
        #     max_tokens=1024,
        # )
        return True, (
            "코드 품질 리뷰 기능은 현재 준비 중입니다. "
            "(향후 LLM 연동 시 자동 활성화)"
        )
