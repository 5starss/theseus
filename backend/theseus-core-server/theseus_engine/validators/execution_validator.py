"""Execution Validator: 상태 변경(Mutating) 작업 안전성 검증기.

에이전트가 실행하는 도구(Tool)의 인자에 포함된 API 호출이나
파일 변경 작업이 안전한지 검증합니다.

기본 모드: Regex (패턴 매칭, 비용 0)
고급 모드: LLM (에이전트 판단, THESEUS_USE_LLM_VALIDATOR=true)

OpenHarness의 CommandHookDefinition / AgentHookDefinition을
래핑하여 PRE_TOOL_USE Hook 파이프라인에 연결할 수 있습니다.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Tuple

from theseus_engine.observability.tracer import (
    theseus_traceable,
)

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 위험 패턴 정의
# ------------------------------------------------------------------

# HTTP 상태 변경 메서드 패턴
_MUTATING_HTTP_PATTERN = re.compile(
    r"\b(requests\.(post|put|patch|delete)|"
    r"httpx\.(post|put|patch|delete)|"
    r"\.post\(|\.put\(|\.patch\(|\.delete\()",
    re.IGNORECASE,
)

# 파일 시스템 파괴 패턴
_FS_DESTRUCTIVE_PATTERN = re.compile(
    r"\b(os\.(remove|unlink|rmdir|rename|replace)"
    r"|shutil\.(rmtree|move|copy2?)"
    r"|pathlib\.Path.*\.(unlink|rmdir))",
    re.IGNORECASE,
)

# ------------------------------------------------------------------
# Bash 전용 위험 패턴
# ------------------------------------------------------------------

# 파일시스템 파괴 명령어 (rm -rf, dd, mkfs 등)
_BASH_DESTRUCTIVE_PATTERN = re.compile(
    r"(rm\s+-[a-z]*r[a-z]*f"           # rm -rf
    r"|rm\s+-[a-z]*f[a-z]*r"           # rm -fr
    r"|rm\s+--force\s+-r"
    r"|\bdd\s+if="                      # dd if=/dev/zero of=...
    r"|\bmkfs\."                        # mkfs.ext4, mkfs.vfat 등
    r"|\bformat\s+[a-z]:"              # Windows: format C:
    r"|\bshred\s+"
    r"|\bwipefs\s+)",
    re.IGNORECASE,
)

# 원격 코드 실행 패턴 (curl|bash, eval 등)
_BASH_RCE_PATTERN = re.compile(
    r"(curl\s+.+\|\s*(ba)?sh"
    r"|wget\s+.+\|\s*(ba)?sh"
    r"|curl\s+.+\|\s*python3?"
    r"|wget\s+.+\|\s*python3?"
    r"|\beval\s*\$\("                  # eval $(...)
    r"|\beval\s+`"                     # eval `...`
    r"|python3?\s+-c\s+['\"]import"   # python -c "import os; os.system(...)"
    r"|\bbase64\s+-d\s+.*\|\s*(ba)?sh)",
    re.IGNORECASE | re.DOTALL,
)

# 권한 상승 패턴 (sudo 파괴 명령, chmod 777 등)
_BASH_PRIVILEGE_PATTERN = re.compile(
    r"(\bsudo\s+(rm|dd|mkfs|wipefs|shred)"
    r"|\bsudo\s+chmod\s+-[a-z]*R[a-z]*\s+777"
    r"|\bchmod\s+-[a-z]*R[a-z]*\s+777"
    r"|\bchown\s+-[a-z]*R[a-z]*\s+root"
    r"|\bsu\s*-\s*root)",
    re.IGNORECASE,
)

# 시스템 경로 탈출 / 덮어쓰기 패턴
_BASH_PATH_TRAVERSAL_PATTERN = re.compile(
    r"(>\s*/etc/"
    r"|>\s*/bin/"
    r"|>\s*/usr/"
    r"|>\s*/boot/"
    r"|>\s*/sys/"
    r"|>\s*/proc/"
    r"|\.\./\.\./\.\./)",              # 3단계 이상 상위 탐색
    re.IGNORECASE,
)


class ExecutionValidator:
    """도구 실행 인자에서 상태 변경(Mutating) 작업을 탐지합니다.

    기본(Default)은 Regex 패턴 매칭 방식이며,
    `THESEUS_USE_LLM_VALIDATOR=true` 환경변수가 설정되면
    LLM 기반 심층 분석 모드로 전환됩니다.
    """

    @classmethod
    @theseus_traceable(
        run_type="tool",
        name="validate_execution",
        tags=["validator", "execution"],
    )
    def validate(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """도구 실행 전 인자의 안전성을 검증합니다.

        Args:
            tool_name: 실행 대상 도구명.
            tool_input: 도구에 전달될 인자 딕셔너리.

        Returns:
            (안전 여부, 메시지) 튜플.
        """
        use_llm = (
            os.getenv("THESEUS_USE_LLM_VALIDATOR", "false")
            .lower() == "true"
        )

        if use_llm:
            return cls._validate_with_llm(
                tool_name, tool_input,
            )
        return cls._validate_with_regex(
            tool_name, tool_input,
        )

    # ------------------------------------------------------------------
    # Regex 기반 검증 (Default)
    # ------------------------------------------------------------------

    @classmethod
    def _validate_with_regex(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Detects dangerous state changes with Regex pattern matching."""
        warnings: List[str] = []
        serialized = str(tool_input)

        if _MUTATING_HTTP_PATTERN.search(serialized):
            warnings.append(
                f"[Execution] Tool '{tool_name}' arguments contain "
                f"HTTP mutating requests (POST/PUT/DELETE) detected."
            )

        if _FS_DESTRUCTIVE_PATTERN.search(serialized):
            warnings.append(
                f"[Execution] Tool '{tool_name}' arguments contain "
                f"destructive filesystem operations (remove/rmtree etc.) detected."
            )

        # bash 툴 전용 위험 패턴 검사
        if tool_name == "bash":
            command = str(tool_input.get("command", ""))

            if _BASH_DESTRUCTIVE_PATTERN.search(command):
                warnings.append(
                    f"[Bash] 파일시스템 파괴 명령어 패턴 감지 "
                    f"(rm -rf / dd / mkfs 등): '{command[:80]}'"
                )

            if _BASH_RCE_PATTERN.search(command):
                warnings.append(
                    f"[Bash] 원격 코드 실행 패턴 감지 "
                    f"(curl|bash / eval 등): '{command[:80]}'"
                )

            if _BASH_PRIVILEGE_PATTERN.search(command):
                warnings.append(
                    f"[Bash] 권한 상승 위험 명령어 감지 "
                    f"(sudo rm / chmod 777 등): '{command[:80]}'"
                )

            if _BASH_PATH_TRAVERSAL_PATTERN.search(command):
                warnings.append(
                    f"[Bash] 시스템 경로 탈출/덮어쓰기 패턴 감지 "
                    f"(> /etc/ 등): '{command[:80]}'"
                )

        if warnings:
            detail = "\n".join(f"  - {w}" for w in warnings)
            log.warning(
                "Execution validation warning (%d items):\n%s",
                len(warnings), detail,
            )
            return False, (
                f"Execution validation warning "
                f"({len(warnings)} items):\n" + detail
            )

        return True, "Execution validation passed."

    # ------------------------------------------------------------------
    # LLM-based validation (Toggle)
    # ------------------------------------------------------------------

    @classmethod
    def _validate_with_llm(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """LLM을 활용한 심층 안전성 분석.

        Note:
            이 메서드는 현재 뼈대(Stub)만 구현되어 있습니다.
            향후 TheseusLLMClient와 연동하여 실제 LLM 호출로
            대체할 예정입니다.
        """
        log.info(
            "[LLM Validator] 도구 '%s'에 대한 "
            "LLM 기반 Execution 검증 요청 (미구현, Regex로 폴백)",
            tool_name,
        )
        # TODO: TheseusLLMClient를 통해 실제 LLM 호출 구현
        # Prompt: "Is this tool execution safe and non-destructive?
        #          Tool: {tool_name}, Arguments: {tool_input}"
        return cls._validate_with_regex(
            tool_name, tool_input,
        )
