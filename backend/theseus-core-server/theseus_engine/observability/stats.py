"""Theseus 인메모리 세션 통계 시스템.

Reservoir Sampling 기반 히스토그램으로 툴 실행 시간, LLM 쿼리 시간,
RAG 검색 시간 등을 경량으로 측정합니다. LangSmith 없이도 즉시 동작합니다.
"""

from __future__ import annotations

import random
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger(__name__)

_RESERVOIR_SIZE = 512


# ---------------------------------------------------------------------------
# 핵심 데이터 구조
# ---------------------------------------------------------------------------

@dataclass
class Histogram:
    """Reservoir Sampling(Algorithm R) 기반 히스토그램."""

    _reservoir: list = field(default_factory=list, repr=False)
    _count: int = 0
    _sum: float = 0.0
    _min: float = float("inf")
    _max: float = float("-inf")

    def observe(self, value: float) -> None:
        self._count += 1
        self._sum += value
        self._min = min(self._min, value)
        self._max = max(self._max, value)

        if len(self._reservoir) < _RESERVOIR_SIZE:
            self._reservoir.append(value)
        else:
            idx = random.randint(0, self._count - 1)
            if idx < _RESERVOIR_SIZE:
                self._reservoir[idx] = value

    def percentile(self, p: float) -> float:
        if not self._reservoir:
            return 0.0
        sorted_r = sorted(self._reservoir)
        idx = int(len(sorted_r) * p / 100)
        return sorted_r[min(idx, len(sorted_r) - 1)]

    @property
    def avg(self) -> float:
        return self._sum / self._count if self._count else 0.0

    @property
    def count(self) -> int:
        return self._count

    @property
    def min_val(self) -> float:
        return self._min if self._count else 0.0

    @property
    def max_val(self) -> float:
        return self._max if self._count else 0.0


@dataclass
class HistogramReport:
    count: int
    avg: float
    min_val: float
    max_val: float
    p50: float
    p95: float
    p99: float


@dataclass
class StatsReport:
    tool_durations: Dict[str, HistogramReport]
    tool_call_counts: Dict[str, int]
    tool_error_counts: Dict[str, int]
    rag_retrieval: Optional[HistogramReport]
    llm_query: Optional[HistogramReport]
    llm_input_tokens: Optional[HistogramReport]
    llm_output_tokens: Optional[HistogramReport]
    hitl_prompt_count: int
    hitl_blocked_count: int
    hitl_always_allow_count: int


# ---------------------------------------------------------------------------
# SessionStats 싱글톤
# ---------------------------------------------------------------------------

class SessionStats:
    """세션 단위 인메모리 통계 수집기 (싱글톤).

    engine_builder.setup_engine() 호출 시 reset()으로 초기화.
    TheseusHookExecutor, ToolRetriever에서 observe/increment 호출.
    """

    _instance: Optional["SessionStats"] = None

    def __init__(self) -> None:
        self._histograms: Dict[str, Histogram] = {}
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        # 툴별 타이머 시작 시각 (PRE → POST 구간 측정용)
        self._tool_timers: Dict[str, float] = {}

    # --- 싱글톤 접근 ---

    @classmethod
    def get(cls) -> "SessionStats":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> "SessionStats":
        """세션 시작 시 통계를 초기화합니다."""
        cls._instance = cls()
        return cls._instance

    # --- 기록 메서드 ---

    def observe(self, metric: str, value_ms: float) -> None:
        if metric not in self._histograms:
            self._histograms[metric] = Histogram()
        self._histograms[metric].observe(value_ms)

    def increment(self, metric: str, delta: int = 1) -> None:
        self._counters[metric] = self._counters.get(metric, 0) + delta

    def set_gauge(self, metric: str, value: float) -> None:
        self._gauges[metric] = value

    # --- 툴 타이머 헬퍼 ---

    def tool_start(self, tool_name: str) -> None:
        self._tool_timers[tool_name] = time.monotonic()

    def tool_end(self, tool_name: str, is_error: bool = False) -> None:
        start = self._tool_timers.pop(tool_name, None)
        if start is not None:
            duration_ms = (time.monotonic() - start) * 1000
            self.observe(f"tool.{tool_name}.duration_ms", duration_ms)
        self.increment(f"tool.{tool_name}.call_count")
        if is_error:
            self.increment(f"tool.{tool_name}.error_count")

    # --- 보고서 생성 ---

    def _make_report(self, h: Histogram) -> HistogramReport:
        return HistogramReport(
            count=h.count,
            avg=round(h.avg, 2),
            min_val=round(h.min_val, 2),
            max_val=round(h.max_val, 2),
            p50=round(h.percentile(50), 2),
            p95=round(h.percentile(95), 2),
            p99=round(h.percentile(99), 2),
        )

    def get_report(self) -> StatsReport:
        # 툴별 duration 히스토그램 수집
        tool_durations: Dict[str, HistogramReport] = {}
        for key, hist in self._histograms.items():
            if key.startswith("tool.") and key.endswith(".duration_ms"):
                tool_name = key[5:-12]
                tool_durations[tool_name] = self._make_report(hist)

        # 툴별 호출/에러 카운터
        tool_call_counts: Dict[str, int] = {}
        tool_error_counts: Dict[str, int] = {}
        for key, val in self._counters.items():
            if key.startswith("tool.") and key.endswith(".call_count"):
                tool_call_counts[key[5:-11]] = val
            elif key.startswith("tool.") and key.endswith(".error_count"):
                tool_error_counts[key[5:-12]] = val

        def _get_hist(metric: str) -> Optional[HistogramReport]:
            h = self._histograms.get(metric)
            return self._make_report(h) if h and h.count else None

        return StatsReport(
            tool_durations=tool_durations,
            tool_call_counts=tool_call_counts,
            tool_error_counts=tool_error_counts,
            rag_retrieval=_get_hist("rag.retrieval_ms"),
            llm_query=_get_hist("llm.query_ms"),
            llm_input_tokens=_get_hist("llm.input_tokens"),
            llm_output_tokens=_get_hist("llm.output_tokens"),
            hitl_prompt_count=self._counters.get("hitl.prompt_count", 0),
            hitl_blocked_count=self._counters.get("hitl.blocked_count", 0),
            hitl_always_allow_count=self._counters.get("hitl.always_allow_count", 0),
        )

    def format_report(self) -> str:
        """CLI /stats 명령용 포맷된 보고서 문자열을 반환합니다."""
        r = self.get_report()
        lines = ["[Stats] 세션 통계", "-" * 56]

        # 툴 실행 시간
        if r.tool_durations:
            lines.append("\n[툴 실행 시간]")
            all_tools = set(r.tool_durations) | set(r.tool_call_counts)
            for name in sorted(all_tools):
                hist = r.tool_durations.get(name)
                calls = r.tool_call_counts.get(name, 0)
                errors = r.tool_error_counts.get(name, 0)
                if hist:
                    lines.append(
                        f"  {name:<20} p50:{hist.p50:>7.0f}ms  "
                        f"p95:{hist.p95:>7.0f}ms  "
                        f"호출:{calls:>3}  에러:{errors:>2}"
                    )
                else:
                    lines.append(
                        f"  {name:<20} (시간 미측정)  "
                        f"호출:{calls:>3}  에러:{errors:>2}"
                    )

        # RAG 검색
        if r.rag_retrieval:
            lines.append("\n[RAG 검색]")
            h = r.rag_retrieval
            lines.append(
                f"  {'retrieval':<20} p50:{h.p50:>7.0f}ms  "
                f"p95:{h.p95:>7.0f}ms  호출:{h.count:>3}"
            )

        # LLM 쿼리
        if r.llm_query:
            lines.append("\n[LLM 쿼리]")
            h = r.llm_query
            lines.append(
                f"  {'query':<20} p50:{h.p50:>7.0f}ms  "
                f"p95:{h.p95:>7.0f}ms  호출:{h.count:>3}"
            )
        if r.llm_input_tokens:
            h = r.llm_input_tokens
            lines.append(f"  input_tokens         avg:{h.avg:>8,.0f}  max:{h.max_val:>10,.0f}")
        if r.llm_output_tokens:
            h = r.llm_output_tokens
            lines.append(f"  output_tokens        avg:{h.avg:>8,.0f}  max:{h.max_val:>10,.0f}")

        # HITL
        if r.hitl_prompt_count > 0:
            lines.append("\n[HITL]")
            lines.append(
                f"  프롬프트:{r.hitl_prompt_count}회  "
                f"거부:{r.hitl_blocked_count}회  "
                f"항상허용 캐시:{r.hitl_always_allow_count}개"
            )

        if len(lines) <= 2:
            lines.append("  (아직 수집된 통계가 없습니다)")

        lines.append("-" * 56)
        return "\n".join(lines)
