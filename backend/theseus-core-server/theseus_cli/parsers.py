"""Plan JSON 파싱, 피드백 처리, 프롬프트 조립 — 순수 함수 모음."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from theseus_cli.ui import display_plan

if TYPE_CHECKING:
    from theseus_engine.models.state import TheseusStateMachine, PlanPhase


_TASK_FIELDS = {
    "title", "problem", "solution", "target_files", "integration_points",
    "expected_effect", "description", "tier", "status",
}
_PLAN_SECTIONS = {"context", "verification", "action_plan", "goal"}
_SECTION_SUBFIELDS = {
    "context":     {"current_state", "problem_analysis", "affected_files", "risks"},
    "verification":{"test_commands", "manual_checks", "success_criteria"},
    "action_plan": {"immediate", "sequential_dependencies", "estimated_turns"},
}


def extract_plan_json(response_text: str) -> dict | None:
    match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def parse_plan_feedback(line: str, plan_json_str: str) -> dict | None:
    """구조화 피드백 입력을 파싱합니다.

    지원 형식:
      1. task-1: 피드백
      2. task-1.solution: 피드백
      3. verification.success_criteria: 피드백
      4. context.risks: 피드백
    """
    if not plan_json_str:
        return None
    try:
        plan_data = json.loads(plan_json_str)
    except json.JSONDecodeError:
        return None

    m = re.match(r'^([a-zA-Z0-9_-]+)(?:\.([a-zA-Z_]+))?\s*:\s*(.+)$', line.strip(), re.DOTALL)
    if not m:
        return None

    target, field, feedback = m.group(1), m.group(2), m.group(3).strip()
    task_ids = {t["id"] for t in plan_data.get("tasks", [])}

    if target in task_ids:
        if field and field not in _TASK_FIELDS:
            return None
        return {"target_type": "task", "target": target, "field": field, "feedback": feedback}

    if target in _PLAN_SECTIONS:
        valid = _SECTION_SUBFIELDS.get(target, set())
        if field and field not in valid:
            return None
        return {"target_type": "section", "target": target, "field": field, "feedback": feedback}

    return None


def build_feedback_prompt(parsed: dict, plan_json_str: str) -> str:
    target_type = parsed["target_type"]
    target      = parsed["target"]
    field       = parsed.get("field")
    feedback    = parsed["feedback"]

    if target_type == "task":
        if field:
            location    = f"the '{field}' field of task '{target}'"
            instruction = (f"Apply the feedback above to modify ONLY the '{field}' field of that task, "
                           f"then output the entire plan again in the same JSON format.")
        else:
            location    = f"task '{target}'"
            instruction = ("Apply the feedback above to modify that task (and related sub-tasks if necessary), "
                           "then output the entire plan again in the same JSON format.")
    else:
        if field:
            location    = f"the '{field}' field of the '{target}' section"
            instruction = (f"Apply the feedback above to modify ONLY the '{target}.{field}' field, "
                           f"then output the entire plan again in the same JSON format.")
        else:
            location    = f"the entire '{target}' section"
            instruction = (f"Apply the feedback above to modify the '{target}' section, "
                           f"then output the entire plan again in the same JSON format.")

    return (
        f"Revision request for {location} in the plan below:\n\n"
        f"Feedback: {feedback}\n\n"
        f"Current plan:\n```json\n{plan_json_str}\n```\n\n"
        f"{instruction}"
    )


def handle_plan_draft(sm: "TheseusStateMachine", response_text: str) -> None:
    """LLM 응답에서 JSON 계획을 추출하고 상태를 WAIT_FOR_REVIEW로 전환합니다."""
    from theseus_engine.models.state import PlanPhase

    plan_data = extract_plan_json(response_text)
    if plan_data:
        sm.plan = json.dumps(plan_data, ensure_ascii=False, indent=2)
        try:
            Path("temp").mkdir(exist_ok=True)
            with open("temp/plan_refactored.json", "w", encoding="utf-8") as f:
                json.dump(plan_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        display_plan(plan_data)
        print("\n" + "-" * 60)
        print("[*] 계획이 작성되었습니다. 'approve' 또는 '/approve'를 입력하여 실행하거나,")
        print("[*] 수정할 내용(피드백)을 텍스트로 입력해 주세요.")
        print("-" * 60 + "\n")
    else:
        sm.plan = response_text
        print("\n[!] 계획 JSON 파싱 실패. 원문을 계획으로 저장합니다.")
        print("[*] 'approve' 또는 '/approve'로 실행하거나 피드백을 입력하세요.\n")

    sm.set_plan_phase(PlanPhase.WAIT_FOR_REVIEW)
