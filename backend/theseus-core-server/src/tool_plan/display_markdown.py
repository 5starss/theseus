from __future__ import annotations

from typing import Any


def build_plan_display_markdown(snapshot: dict[str, Any]) -> str:
    lines = [f"## {snapshot['title']}"]
    summary = str(snapshot.get("summary") or "").strip()
    if summary:
        lines.extend(["", summary])

    lines.extend(["", "### 주요 작업"])
    for index, block in enumerate(snapshot["blocks"], start=1):
        title = str(block.get("title") or f"작업 {index}").strip()
        lines.append(f"{index}. **{title}**")
        display_content = _display_block_content(str(block.get("content") or ""))
        if display_content:
            lines.extend(f"   - {line}" for line in display_content)

    constraints = [str(item).strip() for item in snapshot.get("constraints", []) if str(item).strip()]
    if constraints:
        lines.extend(["", "### 주의 사항"])
        lines.extend(f"- {item}" for item in constraints)

    alternative_lines = _display_alternatives(snapshot.get("alternatives") or [])
    if alternative_lines:
        lines.extend(["", "### 대안 / Plan B"])
        lines.extend(f"- {line}" for line in alternative_lines)

    execution_lines = _display_execution_spec(snapshot.get("executionSpec") or {})
    if execution_lines:
        lines.extend(["", "### 실행 스펙"])
        lines.extend(f"- {line}" for line in execution_lines)

    validation_warnings = [
        str(item).strip()
        for item in snapshot.get("validationWarnings", [])
        if str(item).strip()
    ]
    if validation_warnings:
        lines.extend(["", "### 보완 필요"])
        lines.append(
            "- 실행 스펙 검증이 `warn` 모드라 저장은 허용했지만, "
            "아래 항목은 승인/구현 전에 보완하는 것이 좋습니다."
        )
        lines.extend(f"- {item}" for item in validation_warnings[:10])

    verification_lines = _display_verification(snapshot.get("verification") or {})
    if verification_lines:
        lines.extend(["", "### 검증 기준"])
        lines.extend(f"- {line}" for line in verification_lines)
    return "\n".join(lines).strip()


def _display_block_content(content: str) -> list[str]:
    label_map = {
        "Problem": "문제",
        "Solution": "해결 방향",
        "Description": "구현 내용",
        "Expected effect": "기대 효과",
        "Plan B": "대안",
        "Target files": "영향 파일",
        "Integration points": "연동 지점",
        "Dependencies": "의존 관계",
    }
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            label, value = line.split(":", 1)
            display_label = label_map.get(label.strip())
            if display_label:
                lines.append(f"**{display_label}**: {value.strip()}")
                continue
        lines.append(line)
    return lines


def _display_alternatives(alternatives: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for index, alternative in enumerate(alternatives, start=1):
        title = str(
            alternative.get("title")
            or alternative.get("name")
            or f"대안 {index}"
        ).strip()
        reason = str(
            alternative.get("reason")
            or alternative.get("why")
            or alternative.get("description")
            or ""
        ).strip()
        tradeoffs = alternative.get("tradeoffs") or alternative.get("tradeoff")
        when_to_use = alternative.get("when_to_use") or alternative.get("whenToUse")
        parts = [f"**{title}**"]
        if reason:
            parts.append(reason)
        if tradeoffs:
            parts.append(f"트레이드오프: {tradeoffs}")
        if when_to_use:
            parts.append(f"적용 조건: {when_to_use}")
        lines.append(" - ".join(str(part) for part in parts if str(part).strip()))
    return lines


def _display_execution_spec(execution_spec: dict[str, Any]) -> list[str]:
    if not isinstance(execution_spec, dict) or not execution_spec:
        return []

    lines: list[str] = []
    tool_name = str(execution_spec.get("tool_name") or "").strip()
    if tool_name:
        lines.append(f"도구 이름: `{tool_name}`")

    permission_level = execution_spec.get("permissionLevel")
    if permission_level is None:
        permission_level = execution_spec.get("permission_level")
    if permission_level is not None and str(permission_level).strip():
        line = f"권한 레벨: `{str(permission_level).strip()}`"
        rationale = str(execution_spec.get("permission_rationale") or "").strip()
        if rationale:
            line += f" - {rationale}"
        lines.append(line)

    validation_strategy = str(execution_spec.get("validation_strategy") or "").strip()
    if validation_strategy:
        lines.append(f"검증 전략: `{validation_strategy}`")

    status_values = execution_spec.get("status_values")
    if isinstance(status_values, list) and status_values:
        lines.append(
            "상태값: "
            + ", ".join(f"`{str(item).strip()}`" for item in status_values if str(item).strip())
        )

    inputs = execution_spec.get("inputs")
    if isinstance(inputs, list) and inputs:
        input_names = [
            str(item.get("name") or item.get("key") or "").strip()
            for item in inputs
            if isinstance(item, dict)
        ]
        input_names = [name for name in input_names if name]
        if input_names:
            lines.append("입력값: " + ", ".join(f"`{name}`" for name in input_names[:8]))

    steps = execution_spec.get("steps")
    if isinstance(steps, list) and steps:
        step_titles: list[str] = []
        for step in steps[:8]:
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("step_id") or step.get("id") or "").strip()
            description = str(step.get("description") or "").strip()
            command_count = len(step.get("commands") or []) if isinstance(step.get("commands"), list) else 0
            label = step_id or description or "step"
            suffix = f" ({command_count} command)" if command_count == 1 else f" ({command_count} commands)"
            step_titles.append(f"`{label}`{suffix}")
        if step_titles:
            lines.append("실행 단계: " + ", ".join(step_titles))

    mvp_exclusions = execution_spec.get("mvp_exclusions")
    if isinstance(mvp_exclusions, list) and mvp_exclusions:
        lines.append(
            "MVP 제외: "
            + ", ".join(str(item).strip() for item in mvp_exclusions[:8] if str(item).strip())
        )

    outputs = execution_spec.get("outputs")
    if isinstance(outputs, dict):
        fields = outputs.get("required_result_fields")
        if isinstance(fields, list) and fields:
            lines.append(
                "결과 필드: "
                + ", ".join(f"`{str(item).strip()}`" for item in fields if str(item).strip())
            )

    return lines


def _display_verification(verification: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    success = verification.get("success_criteria")
    if success:
        lines.append(f"성공 기준: {success}")
    manual_checks = verification.get("manual_checks")
    if isinstance(manual_checks, list):
        lines.extend(str(item) for item in manual_checks if str(item).strip())
    elif manual_checks:
        lines.append(str(manual_checks))
    return lines
