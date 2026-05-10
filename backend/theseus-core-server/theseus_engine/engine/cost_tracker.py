"""Theseus 세션 비용 및 토큰 추적기.

멀티모델 환경(GPT-4o, Gemini, Claude)에서 토큰 소비량과 USD 비용을
세션 단위로 집계합니다. LangSmith 없이도 즉시 동작합니다.

단가 오버라이드:
  THESEUS_PRICING_TABLE 환경변수에 JSON 문자열로 단가를 재정의할 수 있습니다.
  예: '{"gpt-4o": {"input": 2.5, "output": 10.0}}'
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 기본 단가표 (USD / 1M tokens)
# ---------------------------------------------------------------------------

_DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-4o":             {"input": 2.50,  "output": 10.00, "cache_read": 1.25,  "cache_write": 0.0},
    "gpt-4o-mini":        {"input": 0.15,  "output": 0.60,  "cache_read": 0.075, "cache_write": 0.0},
    "gpt-4-turbo":        {"input": 10.00, "output": 30.00, "cache_read": 0.0,   "cache_write": 0.0},
    "o1":                 {"input": 15.00, "output": 60.00, "cache_read": 7.50,  "cache_write": 0.0},
    # Anthropic Claude
    "claude-opus-4":      {"input": 15.00, "output": 75.00, "cache_read": 1.50,  "cache_write": 3.75},
    "claude-sonnet-4":    {"input": 3.00,  "output": 15.00, "cache_read": 0.30,  "cache_write": 3.75},
    "claude-haiku-4":     {"input": 0.80,  "output": 4.00,  "cache_read": 0.08,  "cache_write": 1.00},
    "claude-opus-4-5":    {"input": 15.00, "output": 75.00, "cache_read": 1.50,  "cache_write": 3.75},
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00, "cache_read": 0.30,  "cache_write": 3.75},
    # Google Gemini
    "gemini-2.5-pro":     {"input": 1.25,  "output": 10.00, "cache_read": 0.0,   "cache_write": 0.0},
    "gemini-2.5-flash":   {"input": 0.075, "output": 0.30,  "cache_read": 0.0,   "cache_write": 0.0},
    "gemini-2.0-flash":   {"input": 0.10,  "output": 0.40,  "cache_read": 0.0,   "cache_write": 0.0},
}

_LOG_DIR = Path(os.getenv("THESEUS_DATA_DIR", Path.home() / ".theseus"))
_LOG_FILE = _LOG_DIR / "cost_log.jsonl"


def _load_pricing() -> Dict[str, Dict[str, float]]:
    """환경변수 오버라이드를 적용한 최종 단가표를 반환합니다."""
    pricing = dict(_DEFAULT_PRICING)
    override_json = os.getenv("THESEUS_PRICING_TABLE", "")
    if override_json:
        try:
            overrides = json.loads(override_json)
            for model, rates in overrides.items():
                pricing[model] = rates
            log.info("[CostTracker] 단가 오버라이드 적용: %d개 모델", len(overrides))
        except json.JSONDecodeError as e:
            log.warning("[CostTracker] THESEUS_PRICING_TABLE 파싱 실패: %s", e)
    return pricing


# ---------------------------------------------------------------------------
# 데이터 구조
# ---------------------------------------------------------------------------

@dataclass
class ModelUsage:
    """모델 한 종류의 누적 토큰 사용량."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    call_count: int = 0


@dataclass
class SessionCost:
    """세션 전체 비용 집계."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_tool_calls: int = 0
    model_usage: Dict[str, ModelUsage] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CostTracker 싱글톤
# ---------------------------------------------------------------------------

class CostTracker:
    """세션 단위 비용 추적기 (싱글톤).

    engine_builder.setup_engine()에서 get_or_create()로 초기화.
    UsageEvent 또는 직접 record() 호출로 데이터 수집.
    """

    _instance: Optional["CostTracker"] = None

    def __init__(self) -> None:
        self._pricing = _load_pricing()
        self._session = SessionCost()

    # --- 싱글톤 접근 ---

    @classmethod
    def get_or_create(cls, session_id: Optional[str] = None) -> "CostTracker":
        if cls._instance is None:
            cls._instance = cls()
            if session_id:
                cls._instance._session.session_id = session_id
        return cls._instance

    @classmethod
    def reset(cls) -> "CostTracker":
        """세션 시작 시 추적기를 초기화합니다."""
        cls._instance = cls()
        return cls._instance

    # --- 기록 ---

    def record(self, event: Any) -> None:
        """UsageEvent 또는 dict 형태의 사용량을 기록합니다."""
        # dict 또는 객체 모두 처리
        if isinstance(event, dict):
            model = event.get("model", "unknown")
            input_t = event.get("input_tokens", 0) or 0
            output_t = event.get("output_tokens", 0) or 0
            cache_read = event.get("cache_read_input_tokens", 0) or 0
            cache_write = event.get("cache_creation_input_tokens", 0) or 0
        else:
            model = getattr(event, "model", "unknown") or "unknown"
            input_t = getattr(event, "input_tokens", 0) or 0
            output_t = getattr(event, "output_tokens", 0) or 0
            cache_read = getattr(event, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(event, "cache_creation_input_tokens", 0) or 0

        self.record_usage(model, input_t, output_t, cache_read, cache_write)

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """토큰 사용량을 직접 기록하고 발생 비용(USD)을 반환합니다."""
        cost = self._calculate_cost(
            model, input_tokens, output_tokens,
            cache_read_tokens, cache_creation_tokens,
        )

        # 모델별 집계
        canonical = self._canonical_model(model)
        if canonical not in self._session.model_usage:
            self._session.model_usage[canonical] = ModelUsage()

        mu = self._session.model_usage[canonical]
        mu.input_tokens += input_tokens
        mu.output_tokens += output_tokens
        mu.cache_read_tokens += cache_read_tokens
        mu.cache_creation_tokens += cache_creation_tokens
        mu.cost_usd += cost
        mu.call_count += 1

        # 세션 전체 집계
        self._session.total_cost_usd += cost
        self._session.total_input_tokens += input_tokens
        self._session.total_output_tokens += output_tokens
        self._session.total_cache_read_tokens += cache_read_tokens
        self._session.total_cache_creation_tokens += cache_creation_tokens

        log.debug(
            "[CostTracker] %s: +%d/%d tokens → +$%.6f (total $%.4f)",
            canonical, input_tokens, output_tokens, cost,
            self._session.total_cost_usd,
        )
        return cost

    def increment_tool_calls(self, count: int = 1) -> None:
        self._session.total_tool_calls += count

    # --- 단가 계산 ---

    def _canonical_model(self, model: str) -> str:
        """모델명을 단가표 키로 정규화합니다."""
        model_lower = model.lower()
        for key in self._pricing:
            if key in model_lower:
                return key
        return model_lower

    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_creation_tokens: int,
    ) -> float:
        canonical = self._canonical_model(model)
        rates = self._pricing.get(canonical, {"input": 0.0, "output": 0.0,
                                               "cache_read": 0.0, "cache_write": 0.0})
        cost = (
            input_tokens * rates.get("input", 0.0) / 1_000_000
            + output_tokens * rates.get("output", 0.0) / 1_000_000
            + cache_read_tokens * rates.get("cache_read", 0.0) / 1_000_000
            + cache_creation_tokens * rates.get("cache_write", 0.0) / 1_000_000
        )
        return round(cost, 8)

    # --- 보고서 ---

    def get_session(self) -> SessionCost:
        return self._session

    def format_report(self) -> str:
        """CLI /cost 명령용 포맷된 비용 보고서를 반환합니다."""
        s = self._session
        lines = [
            "비용 세션 요약",
            "-" * 60,
            f"{'모델':<22} {'입력':>8} {'출력':>8} {'캐시히트':>9} {'비용':>10}",
            "-" * 60,
        ]

        for model_name, mu in sorted(
            s.model_usage.items(), key=lambda x: -x[1].cost_usd
        ):
            cache_str = (
                f"{mu.cache_read_tokens:>8,}" if mu.cache_read_tokens else "       -"
            )
            lines.append(
                f"  {model_name:<20} {mu.input_tokens:>8,} {mu.output_tokens:>8,} "
                f"{cache_str} ${mu.cost_usd:>9.4f}"
            )

        lines.append("-" * 60)
        total_cache = (
            f"{s.total_cache_read_tokens:>8,}" if s.total_cache_read_tokens else "       -"
        )
        lines.append(
            f"  {'합계':<20} {s.total_input_tokens:>8,} {s.total_output_tokens:>8,} "
            f"{total_cache} ${s.total_cost_usd:>9.4f}"
        )
        lines.append(f"  툴 호출 횟수: {s.total_tool_calls}회")
        return "\n".join(lines)

    # --- 영속화 ---

    def save(self) -> None:
        """현재 세션 비용을 JSONL 로그에 추가합니다."""
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                "session_id": self._session.session_id,
                "started_at": self._session.started_at,
                "ended_at": datetime.utcnow().isoformat(),
                "total_cost_usd": self._session.total_cost_usd,
                "total_input_tokens": self._session.total_input_tokens,
                "total_output_tokens": self._session.total_output_tokens,
                "total_tool_calls": self._session.total_tool_calls,
                "model_usage": {
                    k: {
                        "input_tokens": v.input_tokens,
                        "output_tokens": v.output_tokens,
                        "cache_read_tokens": v.cache_read_tokens,
                        "cost_usd": v.cost_usd,
                        "call_count": v.call_count,
                    }
                    for k, v in self._session.model_usage.items()
                },
            }
            with _LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as e:
            log.warning("[CostTracker] 비용 로그 저장 실패: %s", e)

    async def save_async(self) -> None:
        """save()의 비동기 버전 — 이벤트 루프를 차단하지 않습니다."""
        await asyncio.to_thread(self.save)
