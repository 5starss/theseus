"""Shared custom-tool repair loop for Theseus runtimes.

The module is intentionally server-independent so CLI, TUI, extension runner,
and Core server ToolBuild can reuse the same repair policy.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, TypeVar

from theseus_engine.models.messages import ConversationMessage
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
)


COMMON_CUSTOM_TOOL_SECURITY_RULES = """\
Generated Theseus custom tool security rules:
- Do not import or call subprocess, os.system, os.popen, shutil, socket, ctypes, multiprocessing, signal, pty, resource, tempfile, webbrowser, pickle, or shelve.
- Do not execute shell commands or arbitrary local programs from generated custom tools.
- Do not read or write arbitrary local files unless the approved plan explicitly names safe read-only paths.
- For system metrics, prefer psutil and read-only /proc or /sys data. Do not call nvidia-smi directly from a generated custom tool.
- If a core requirement depends on a prohibited command or module, return decision=needs_user_feedback instead of silently removing that capability.
- On every repair attempt, choose a different implementation approach from the failed one. Do not reintroduce a banned module, function, or exact failing pattern.
"""


T = TypeVar("T")
S = TypeVar("S")


@dataclass(frozen=True)
class ToolRepairPolicy:
    max_attempts: int = 2
    force_alternative_approach: bool = True

    @classmethod
    def from_env(cls, *, default_attempts: int = 2) -> "ToolRepairPolicy":
        raw = (
            os.getenv("THESEUS_TOOL_REPAIR_MAX_ATTEMPTS")
            or os.getenv("CORE_TOOL_BUILD_MAX_REPAIR_ATTEMPTS")
            or str(default_attempts)
        )
        try:
            attempts = max(int(raw), 0)
        except ValueError:
            attempts = max(default_attempts, 0)
        return cls(max_attempts=attempts)


@dataclass
class ToolRepairFailure(RuntimeError):
    stage: str
    code: str
    message: str
    source_context: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)
        self.code = classify_repair_failure(self.code, self.message)
        self.metadata.setdefault("classifiedCode", self.code)

    @property
    def is_policy_violation(self) -> bool:
        return self.code == "POLICY_VIOLATION"

    @property
    def is_tool_name_conflict(self) -> bool:
        return self.code == "TOOL_NAME_CONFLICT"

    @property
    def is_permission_validation_failure(self) -> bool:
        return self.code == "PERMISSION_VALIDATION_FAILED"

    @property
    def is_dependency_failure(self) -> bool:
        return self.code == "SANDBOX_MISSING_DEPENDENCY"

    @property
    def blocks_automatic_retry(self) -> bool:
        return (
            self.is_tool_name_conflict
            or self.is_permission_validation_failure
            or self.is_dependency_failure
        )

    def to_prompt_text(self) -> str:
        parts = [
            f"stage: {self.stage}",
            f"code: {self.code}",
            f"message: {self.message}",
        ]
        if self.source_context:
            parts.append("source context:\n" + self.source_context)
        if self.metadata:
            parts.append(
                "metadata:\n"
                + json.dumps(self.metadata, ensure_ascii=False, indent=2, default=str)
            )
        return "\n".join(parts)


@dataclass
class ToolRepairResult(Generic[T, S]):
    success: bool
    candidate: T | None = None
    value: S | None = None
    attempts: int = 0
    last_failure: ToolRepairFailure | None = None
    needs_user_feedback: bool = False
    feedback_message: str | None = None
    raw_response: str | None = None

    def final_message(self, policy: ToolRepairPolicy) -> str:
        if self.needs_user_feedback:
            base = self.feedback_message or "사용자 피드백이 필요합니다."
            if self.last_failure is not None and (
                self.last_failure.is_tool_name_conflict
                or self.last_failure.is_permission_validation_failure
                or self.last_failure.is_dependency_failure
            ):
                return base
            if self.last_failure is not None:
                return (
                    f"자동 repair {policy.max_attempts}회 내에서 안전한 대체 구현을 찾지 못했습니다. "
                    f"{base} 마지막 오류: {self.last_failure.message}"
                )
            return base
        if self.last_failure is None:
            return "Tool repair failed without a captured error."
        if policy.max_attempts <= 0:
            return self.last_failure.message
        return (
            f"자동 repair {policy.max_attempts}회 후 실패했습니다. "
            f"마지막 오류: {self.last_failure.message}"
        )


GenerateCallback = Callable[[str], Awaitable[T]]
ValidateCallback = Callable[[T], Awaitable[S]]
ParseCandidateCallback = Callable[[dict[str, Any]], T]
RenderCandidateCallback = Callable[[T | None], Any]
AttemptCallback = Callable[[int, bool], Awaitable[None] | None]


class ToolRepairLoop(Generic[T, S]):
    def __init__(
        self,
        *,
        llm_client: SupportsStreamingMessages,
        model_name: str,
        policy: ToolRepairPolicy | None = None,
        debug_context: dict[str, Any] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.model_name = model_name
        self.policy = policy or ToolRepairPolicy.from_env()
        self.debug_context = debug_context or {}

    async def run(
        self,
        *,
        initial_prompt: str,
        initial_candidate: T | None = None,
        task_context: str,
        candidate_contract: str,
        generate_candidate: GenerateCallback[T],
        validate_candidate: ValidateCallback[T, S],
        parse_candidate_payload: ParseCandidateCallback[T],
        render_candidate: RenderCandidateCallback[T],
        on_attempt: AttemptCallback | None = None,
    ) -> ToolRepairResult[T, S]:
        candidate = initial_candidate
        prompt = initial_prompt
        failures: list[ToolRepairFailure] = []

        for attempt in range(self.policy.max_attempts + 1):
            is_repair = attempt > 0
            if on_attempt is not None:
                maybe = on_attempt(attempt, is_repair)
                if maybe is not None:
                    await maybe

            if candidate is None:
                try:
                    if is_repair:
                        decision, repaired, feedback, raw = await self._request_repair(
                            prompt,
                            parse_candidate_payload=parse_candidate_payload,
                        )
                        if decision == "needs_user_feedback":
                            return ToolRepairResult(
                                success=False,
                                attempts=attempt,
                                last_failure=failures[-1] if failures else None,
                                needs_user_feedback=True,
                                feedback_message=feedback,
                                raw_response=raw,
                            )
                        candidate = repaired
                    else:
                        candidate = await generate_candidate(prompt)
                except ToolRepairFailure as failure:
                    failures.append(failure)
                    should_stop = self._should_stop(failures)
                    if attempt >= self.policy.max_attempts or should_stop:
                        return ToolRepairResult(
                            success=False,
                            attempts=attempt,
                            last_failure=failure,
                            needs_user_feedback=_needs_user_feedback(failure, should_stop),
                            feedback_message=_recovery_feedback_message(failure) if should_stop else None,
                        )
                    prompt = self._build_repair_prompt(
                        task_context=task_context,
                        candidate_contract=candidate_contract,
                        previous_candidate=None,
                        failures=failures,
                        attempt=attempt + 1,
                    )
                    continue

            try:
                value = await validate_candidate(candidate)
                return ToolRepairResult(
                    success=True,
                    candidate=candidate,
                    value=value,
                    attempts=attempt,
                    last_failure=failures[-1] if failures else None,
                )
            except ToolRepairFailure as failure:
                failures.append(failure)
                should_stop = self._should_stop(failures)
                if attempt >= self.policy.max_attempts or should_stop:
                    return ToolRepairResult(
                        success=False,
                        candidate=candidate,
                        attempts=attempt,
                        last_failure=failure,
                        needs_user_feedback=_needs_user_feedback(failure, should_stop),
                        feedback_message=_recovery_feedback_message(failure) if should_stop else None,
                    )

                prompt = self._build_repair_prompt(
                    task_context=task_context,
                    candidate_contract=candidate_contract,
                    previous_candidate=render_candidate(candidate),
                    failures=failures,
                    attempt=attempt + 1,
                )
                try:
                    decision, repaired, feedback, raw = await self._request_repair(
                        prompt,
                        parse_candidate_payload=parse_candidate_payload,
                    )
                except ToolRepairFailure as repair_failure:
                    candidate = None
                    failures.append(repair_failure)
                    should_stop = self._should_stop(failures)
                    if attempt + 1 >= self.policy.max_attempts or should_stop:
                        return ToolRepairResult(
                            success=False,
                            attempts=attempt + 1,
                            last_failure=repair_failure,
                            needs_user_feedback=_needs_user_feedback(repair_failure, should_stop),
                            feedback_message=_recovery_feedback_message(repair_failure) if should_stop else None,
                            raw_response=repair_failure.metadata.get("rawResponse"),
                        )
                    continue

                if decision == "needs_user_feedback":
                    return ToolRepairResult(
                        success=False,
                        candidate=candidate,
                        attempts=attempt + 1,
                        last_failure=failure,
                        needs_user_feedback=True,
                        feedback_message=feedback,
                        raw_response=raw,
                    )
                candidate = repaired

        last_failure = failures[-1] if failures else None
        return ToolRepairResult(success=False, candidate=candidate, last_failure=last_failure)

    async def _request_repair(
        self,
        prompt: str,
        *,
        parse_candidate_payload: ParseCandidateCallback[T],
    ) -> tuple[str, T | None, str | None, str]:
        final_text = ""
        request = ApiMessageRequest(
            model=self.model_name,
            messages=[ConversationMessage.from_user_text(prompt)],
            system_prompt=(
                "You repair Theseus generated custom tool artifacts. "
                "Return strict JSON only. Do not include markdown fences."
            ),
            max_tokens=8192,
            tools=[],
            debug_context=self.debug_context,
        )
        async for event in self.llm_client.stream_message(request):
            if isinstance(event, ApiTextDeltaEvent):
                final_text += event.text
            elif isinstance(event, ApiMessageCompleteEvent):
                final_text = event.message.text or final_text

        try:
            payload = json.loads(extract_json_object(final_text))
        except Exception as exc:
            raise ToolRepairFailure(
                stage="repair_generation",
                code="LLM_OUTPUT_INVALID",
                message=f"Invalid repair LLM output: {exc}",
                metadata={"rawResponse": final_text[:2000]},
            ) from exc

        decision = str(payload.get("decision") or "repair").strip()
        if decision == "needs_user_feedback":
            return decision, None, _feedback_message(payload), final_text
        if decision != "repair":
            raise ToolRepairFailure(
                stage="repair_generation",
                code="LLM_OUTPUT_INVALID",
                message=f"Unsupported repair decision: {decision}",
                metadata={"rawResponse": final_text[:2000]},
            )

        candidate_payload = payload.get("candidate")
        if not isinstance(candidate_payload, dict):
            raise ToolRepairFailure(
                stage="repair_generation",
                code="LLM_OUTPUT_INVALID",
                message="Repair response must include object field 'candidate'.",
                metadata={"rawResponse": final_text[:2000]},
            )
        try:
            candidate = parse_candidate_payload(candidate_payload)
        except Exception as exc:
            raise ToolRepairFailure(
                stage="repair_generation",
                code="LLM_OUTPUT_INVALID",
                message=f"Repair candidate did not match the expected schema: {exc}",
                metadata={"rawResponse": final_text[:2000]},
            ) from exc
        return decision, candidate, None, final_text

    def _build_repair_prompt(
        self,
        *,
        task_context: str,
        candidate_contract: str,
        previous_candidate: Any,
        failures: list[ToolRepairFailure],
        attempt: int,
    ) -> str:
        failure_text = "\n\n".join(
            f"Failure {idx + 1}:\n{failure.to_prompt_text()}"
            for idx, failure in enumerate(failures[-3:])
        )
        previous_text = (
            json.dumps(previous_candidate, ensure_ascii=False, indent=2, default=str)
            if previous_candidate is not None
            else "null"
        )
        repeated_policy = (
            "\nRepeated policy violation rule:\n"
            "- If the same banned module/function appears again, do not try another superficial edit. "
            "Return decision=needs_user_feedback and explain the blocked requirement.\n"
            if len([f for f in failures if f.is_policy_violation]) >= 1
            else ""
        )
        return (
            "Repair a generated Theseus custom tool artifact.\n\n"
            f"Repair attempt: {attempt} of {self.policy.max_attempts}\n\n"
            f"{COMMON_CUSTOM_TOOL_SECURITY_RULES}\n"
            f"{repeated_policy}\n"
            "You must choose a different implementation approach from the failed one. "
            "Do not repeat the same banned import, function, command execution path, "
            "or placeholder-only repair.\n\n"
            "If the approved requirement cannot be safely satisfied under these rules, "
            "return this JSON exactly:\n"
            "{\n"
            '  "decision": "needs_user_feedback",\n'
            '  "message": "short explanation in the user\'s language",\n'
            '  "blockedRequirements": ["..."],\n'
            '  "safeAlternatives": ["..."]\n'
            "}\n\n"
            "Otherwise return this JSON exactly:\n"
            "{\n"
            '  "decision": "repair",\n'
            '  "message": "short repair summary in the user\'s language",\n'
            '  "candidate": { ... corrected candidate object ... }\n'
            "}\n\n"
            f"Task context:\n{task_context}\n\n"
            f"Candidate contract:\n{candidate_contract}\n\n"
            f"Previous candidate:\n{previous_text}\n\n"
            f"Failures:\n{failure_text}\n\n"
            "Return strict JSON only."
        )

    @staticmethod
    def _should_stop(failures: list[ToolRepairFailure]) -> bool:
        if failures and failures[-1].blocks_automatic_retry:
            return True
        policy_failures = [failure for failure in failures if failure.is_policy_violation]
        if len(policy_failures) < 2:
            return False
        first = _policy_signature(policy_failures[-2].message)
        second = _policy_signature(policy_failures[-1].message)
        return bool(first and second and first == second)


def classify_repair_failure(code: str, message: str) -> str:
    normalized = (code or "").strip().upper()
    lowered = message.lower()
    if (
        "sandbox_missing_dependency" in lowered
        or re.search(r"\bno module named ['\"]", lowered)
        or normalized in {"SANDBOX_MISSING_DEPENDENCY", "MISSING_DEPENDENCY"}
    ):
        return "SANDBOX_MISSING_DEPENDENCY"
    if (
        "이미 존재" in lowered
        or "already exists" in lowered
        or "duplicate" in lowered
        or "file name" in lowered
        or "filename" in lowered
        or "module name conflict" in lowered
        or "modulename=" in lowered
        or normalized in {"TOOL_NAME_CONFLICT", "NAME_CONFLICT", "DUPLICATE_TOOL"}
    ):
        return "TOOL_NAME_CONFLICT"
    if "permissionlevel must be an integer" in lowered or "permission_level_not_integer" in lowered:
        return "PERMISSION_VALIDATION_FAILED"
    if (
        "security static analysis failed" in lowered
        or "security policy violation" in lowered
        or "module 'subprocess' is not allowed" in lowered
        or "function 'system()' is not allowed" in lowered
    ):
        return "POLICY_VIOLATION"
    return normalized or "UNKNOWN"


def _needs_user_feedback(failure: ToolRepairFailure, should_stop: bool) -> bool:
    return should_stop and (
        failure.is_policy_violation
        or failure.is_tool_name_conflict
        or failure.is_permission_validation_failure
        or failure.is_dependency_failure
    )


def _recovery_feedback_message(failure: ToolRepairFailure) -> str | None:
    if failure.is_tool_name_conflict:
        return _tool_name_conflict_feedback_message(failure)
    if failure.is_permission_validation_failure:
        return _permission_feedback_message(failure)
    if failure.is_dependency_failure:
        return _dependency_feedback_message(failure)
    if failure.is_policy_violation:
        return _policy_feedback_message(failure)
    return None


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start:end + 1]
    raise ValueError("No JSON object found")


def _feedback_message(payload: dict[str, Any]) -> str:
    message = str(payload.get("message") or "").strip()
    blocked = payload.get("blockedRequirements")
    alternatives = payload.get("safeAlternatives")
    parts = [message or "이 요구사항은 현재 custom tool 보안 정책 안에서 안전하게 구현할 수 없습니다."]
    if isinstance(blocked, list) and blocked:
        parts.append("차단된 요구사항: " + ", ".join(str(item) for item in blocked[:5]))
    if isinstance(alternatives, list) and alternatives:
        parts.append("가능한 대안: " + ", ".join(str(item) for item in alternatives[:5]))
    return " ".join(parts)


def _policy_feedback_message(failure: ToolRepairFailure) -> str:
    signature = _policy_signature(failure.message)
    blocked = signature.replace("module:", "금지 모듈 ").replace("function:", "금지 함수 ")
    if not blocked:
        blocked = "현재 보안 정책에서 금지된 구현 방식"
    return (
        f"{blocked} 때문에 같은 방식의 자동 repair를 중단했습니다. "
        "읽기 전용 API로 요구사항을 만족할 수 있는지 사용자 확인이 필요하거나, "
        "trusted core adapter로 분리해야 합니다."
    )


def _tool_name_conflict_feedback_message(failure: ToolRepairFailure) -> str:
    return (
        "같은 Tool 파일명 또는 moduleName이 이미 존재해 자동 repair를 중단했습니다. "
        "recoverable=true. retry_policy=do_not_retry_same_input. "
        "가능한 다음 조치: 1) 기존 Tool을 재사용합니다. "
        "2) 기존 Tool을 읽고 확장하는 PLAN draft로 바꿉니다. "
        "3) 새 toolName/moduleName/fileName을 제안합니다. "
        "4) 기존 Tool 교체가 필요한지 사용자 승인을 요청합니다. "
        f"원본 오류: {failure.message}"
    )


def _permission_feedback_message(failure: ToolRepairFailure) -> str:
    return (
        "permissionLevel 값이 정수 1~5 범위를 벗어나 자동 repair를 중단했습니다. "
        "recoverable=true. retry_policy=requires_corrected_permission_level. "
        "권한은 위험도나 신뢰도 점수가 아니라 실행 권한 등급입니다. "
        "1~5 중 하나의 정수 permissionLevel로 다시 지정해야 합니다. "
        f"원본 오류: {failure.message}"
    )


def _dependency_feedback_message(failure: ToolRepairFailure) -> str:
    return (
        "sandbox 의존성 누락 때문에 자동 repair를 중단했습니다. "
        "recoverable=true. retry_policy=requires_environment_update. "
        "이미 생성된 draft artifact는 같은 승인 계획에서 재사용/재검증할 수 있으며, "
        "새 Tool 이름으로 반복 생성하지 않아야 합니다. "
        "requirements-sandbox.txt와 Dockerfile.sandbox 기준으로 sandbox image를 rebuild하고 "
        "Core를 재시작한 뒤 같은 승인 작업을 다시 실행해야 합니다. "
        f"원본 오류: {failure.message}"
    )


def _policy_signature(message: str) -> str:
    module_match = re.search(r"Module '([^']+)' is not allowed", message)
    if module_match:
        return f"module:{module_match.group(1)}"
    function_match = re.search(r"Function '([^']+)\(\)' is not allowed", message)
    if function_match:
        return f"function:{function_match.group(1)}"
    return ""
