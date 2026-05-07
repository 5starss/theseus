"""Tool Usage Feedback Logger

실제 에이전트 실행 중 호출된 도구 이름을 JSON 로그로 누적하여,
ToolRetriever의 few-shot 쿼리를 자동으로 보강합니다.

흐름:
  1. theseus_cli.py / engine_builder 에서 도구 실행 이벤트 발생 시
     `record_tool_call(query, tool_name)` 호출
  2. 로그는 .theseus/tool_usage.jsonl 에 누적 (JSONL 형식)
  3. `load_feedback_queries()` 로 집계 → TOOL_EXAMPLE_QUERIES 에 병합
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)

# 로그 파일 위치: 프로젝트 루트 기준 .theseus/tool_usage.jsonl
_LOG_DIR = Path(os.getenv("THESEUS_DATA_DIR", Path.home() / ".theseus"))
_LOG_FILE = _LOG_DIR / "tool_usage.jsonl"

# 도구 1개당 피드백으로 보강할 최대 쿼리 수
_MAX_FEEDBACK_QUERIES_PER_TOOL = 10


def _write_record_sync(record: dict) -> None:
    """동기 파일 쓰기 헬퍼 — asyncio.to_thread()에서 호출됩니다."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_tool_call(user_query: str, tool_name: str) -> None:
    """도구 호출 이벤트를 JSONL 로그에 기록합니다 (동기 컨텍스트용).

    async 컨텍스트에서는 record_tool_call_async()를 사용하세요.

    Args:
        user_query: 도구 호출을 유발한 사용자 쿼리.
        tool_name: 실제 호출된 도구 이름.
    """
    if not user_query or not tool_name:
        return
    try:
        record = {
            "ts": datetime.utcnow().isoformat(),
            "query": user_query[:200],
            "tool": tool_name,
        }
        _write_record_sync(record)
    except OSError as e:
        log.debug("[ToolUsageLogger] 로그 기록 실패: %s", e)


async def record_tool_call_async(user_query: str, tool_name: str) -> None:
    """도구 호출 이벤트를 비동기로 JSONL 로그에 기록합니다.

    이벤트 루프를 차단하지 않도록 파일 I/O를 스레드 풀에 위임합니다.

    Args:
        user_query: 도구 호출을 유발한 사용자 쿼리.
        tool_name: 실제 호출된 도구 이름.
    """
    if not user_query or not tool_name:
        return
    try:
        record = {
            "ts": datetime.utcnow().isoformat(),
            "query": user_query[:200],
            "tool": tool_name,
        }
        await asyncio.to_thread(_write_record_sync, record)
    except OSError as e:
        log.debug("[ToolUsageLogger] 로그 기록 실패: %s", e)


def load_feedback_queries(
    max_per_tool: int = _MAX_FEEDBACK_QUERIES_PER_TOOL,
) -> Dict[str, List[str]]:
    """누적 로그에서 도구별 쿼리 목록을 집계합니다.

    가장 최근 기록을 우선으로 max_per_tool 개까지 반환합니다.

    Args:
        max_per_tool: 도구 1개당 반환할 최대 쿼리 수.

    Returns:
        {tool_name: [query, ...]} 형태의 딕셔너리.
    """
    if not _LOG_FILE.exists():
        return {}

    # 도구별 쿼리 목록 (최신순 누적)
    tool_queries: Dict[str, List[str]] = defaultdict(list)
    try:
        lines = _LOG_FILE.read_text(encoding="utf-8").splitlines()
        # 최신 항목이 마지막에 있으므로 역순으로 읽어 최신 우선 수집
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                tool = rec.get("tool", "")
                query = rec.get("query", "")
                if tool and query:
                    queries = tool_queries[tool]
                    if query not in queries and len(queries) < max_per_tool:
                        queries.append(query)
            except json.JSONDecodeError:
                continue
    except OSError as e:
        log.debug("[ToolUsageLogger] 로그 읽기 실패: %s", e)

    return dict(tool_queries)


def merge_feedback_into_examples(
    base_examples: Dict[str, List[str]],
    max_per_tool: int = _MAX_FEEDBACK_QUERIES_PER_TOOL,
) -> Dict[str, List[str]]:
    """피드백 로그를 기존 TOOL_EXAMPLE_QUERIES에 병합합니다.

    base_examples의 값을 직접 변경하지 않고 새 딕셔너리를 반환합니다.

    Args:
        base_examples: tool_retriever.TOOL_EXAMPLE_QUERIES (원본).
        max_per_tool: 도구 1개당 최종 최대 쿼리 수.

    Returns:
        병합된 새 딕셔너리.
    """
    feedback = load_feedback_queries(max_per_tool=max_per_tool)
    if not feedback:
        return base_examples

    merged: Dict[str, List[str]] = {}
    all_tools = set(base_examples) | set(feedback)

    for tool in all_tools:
        existing = list(base_examples.get(tool, []))
        new_queries = feedback.get(tool, [])
        combined = existing[:]
        for q in new_queries:
            if q not in combined:
                combined.append(q)
        merged[tool] = combined[:max_per_tool]

    added = sum(
        len(merged.get(t, [])) - len(base_examples.get(t, []))
        for t in feedback
    )
    log.info("[ToolUsageLogger] 피드백 병합 완료: +%d 쿼리 보강", added)
    return merged


def get_log_stats() -> Dict[str, int]:
    """로그 통계 (도구별 총 호출 횟수) 를 반환합니다."""
    counts: Dict[str, int] = defaultdict(int)
    if not _LOG_FILE.exists():
        return {}
    try:
        for line in _LOG_FILE.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                tool = rec.get("tool", "")
                if tool:
                    counts[tool] += 1
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
