from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.tool_plan.schemas import ToolPlanRequestEvent


_EXECUTION_SPEC_KEYWORDS = (
    "tool",
    "custom tool",
    "generated tool",
    "remote workspace",
    "deployment",
    "deploy",
    "post-deploy",
    "health check",
    "docker",
    "container",
    "api check",
    "log",
    "resource",
    "monitoring",
    "monitor",
    "툴",
    "도구",
    "생성",
    "만들",
    "원격",
    "리모트",
    "배포",
    "점검",
    "헬스",
    "상태 조회",
    "운영서버",
    "운영 서버",
    "도커",
    "컨테이너",
    "로그",
    "리소스",
    "모니터링",
)
_ALLOWED_EXECUTION_STATUS_VALUES = {"PASS", "WARNING", "FAIL", "SKIPPED", "INFO"}
_READ_ONLY_API_METHODS = {"GET", "HEAD", "OPTIONS"}
_ALLOWED_COMMAND_ROOTS = {
    "docker",
    "df",
    "free",
    "top",
    "uptime",
    "curl",
    "grep",
    "awk",
    "sed",
    "python",
    "python3",
    "node",
    "git",
}
_VERIFICATION_COMMAND_ROOTS = {"python", "python3", "node", "git"}
_ALLOWED_DOCKER_SUBCOMMANDS = {"ps", "inspect", "logs"}
_DENIED_COMMAND_PATTERNS = (
    r"\bdocker\s+exec\b",
    r"\bdocker\s+stop\b",
    r"\bdocker\s+restart\b",
    r"\bdocker\s+rm\b",
    r"\bdocker\s+compose\s+up\b",
    r"\bdocker\s+compose\s+down\b",
    r"\bkubectl\b",
    r"\brm\b",
    r"\bmv\b",
    r"\bcp\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bvi\b",
    r"\bnano\b",
    r"\bsystemctl\b",
    r"\bservice\b",
    r"\bkill\b",
    r"\breboot\b",
    r"\bshutdown\b",
)
_DOCKER_INSPECT_REQUIRED_FIELDS = (
    ".State.Status",
    ".RestartCount",
    ".State.ExitCode",
    ".State.OOMKilled",
    ".State.Health",
    ".State.Health.Status",
)


@dataclass
class ExecutionSpecValidationResult:
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def validate_execution_spec_if_required(
    plan_json: dict[str, Any],
    event: ToolPlanRequestEvent,
    *,
    validation_mode: str,
) -> ExecutionSpecValidationResult:
    """Validate PLAN draft execution_spec without deciding persistence policy.

    The caller decides whether returned errors are hard failures or warnings.
    This keeps server contract handling in planner.py while this module owns
    structural/safety/quality classification.
    """

    if validation_mode == "off":
        return ExecutionSpecValidationResult()

    requires_spec = requires_execution_spec(plan_json, event)
    generated_tool_request = is_generated_tool_request(plan_json, event)
    execution_spec = plan_json.get("execution_spec")
    if not requires_spec and not isinstance(execution_spec, dict):
        return ExecutionSpecValidationResult()

    warnings: list[str] = []
    if not isinstance(execution_spec, dict) or not execution_spec:
        if generated_tool_request:
            execution_spec = default_generated_tool_execution_spec(plan_json)
            plan_json["execution_spec"] = execution_spec
            warnings.append(
                "execution_spec was missing for a generated Theseus custom tool request; "
                "Core normalized it with validation_strategy=core_sandbox_gate. "
                "Review the tool behavior, input schema, output schema, dependency policy, "
                "and exclusions before approval/build."
            )
        else:
            return ExecutionSpecValidationResult(
                errors=[
                    "PLAN draft execution spec invalid: execution_spec is required for "
                    "generated tool, remote, deployment, health check, Docker, API, log, "
                    "resource, or operating-server diagnostic requests."
                ]
            )

    if not isinstance(execution_spec, dict):
        return ExecutionSpecValidationResult(
            errors=[
                "PLAN draft execution spec invalid: execution_spec is required for "
                "generated tool, remote, deployment, health check, Docker, API, log, "
                "resource, or operating-server diagnostic requests."
            ]
        )

    errors: list[str] = []
    _validate_execution_spec_validation_strategy(
        execution_spec,
        generated_tool_request,
        errors,
    )
    _validate_execution_spec_shape(execution_spec, errors)
    _validate_execution_spec_command_policy(execution_spec, errors)
    _validate_execution_spec_api_checks(execution_spec, errors)
    _validate_execution_spec_steps(execution_spec, errors)
    warnings.extend(
        collect_execution_spec_quality_warnings(
            execution_spec,
            generated_tool_request=generated_tool_request,
        )
    )
    return ExecutionSpecValidationResult(warnings=warnings[:20], errors=errors[:20])


def requires_execution_spec(plan_json: dict[str, Any], event: ToolPlanRequestEvent) -> bool:
    if event.remote_workspace_id is not None:
        return True
    searchable = [
        getattr(event, "prompt", ""),
        plan_json.get("goal"),
        plan_json.get("summary"),
        plan_json.get("title"),
        json.dumps(plan_json.get("context") or {}, ensure_ascii=False),
        json.dumps(plan_json.get("tasks") or [], ensure_ascii=False),
    ]
    text = "\n".join(str(item or "") for item in searchable).lower()
    return any(keyword.lower() in text for keyword in _EXECUTION_SPEC_KEYWORDS)


def is_generated_tool_request(plan_json: dict[str, Any], event: ToolPlanRequestEvent) -> bool:
    searchable = [
        getattr(event, "prompt", ""),
        plan_json.get("goal"),
        plan_json.get("summary"),
        plan_json.get("title"),
        json.dumps(plan_json.get("context") or {}, ensure_ascii=False),
        json.dumps(plan_json.get("tasks") or [], ensure_ascii=False),
        json.dumps(plan_json.get("execution_spec") or {}, ensure_ascii=False),
    ]
    text = "\n".join(str(item or "") for item in searchable).lower()
    return any(
        keyword in text
        for keyword in (
            "custom tool",
            "generated tool",
            "create_tool",
            "theseus custom tool",
            "tool_name",
            "tool",
            "tool 만들",
            "tool 생성",
            "tool 만들어",
            "툴",
            "도구",
            "생성할 tool",
            "커스텀",
        )
    )


def default_generated_tool_execution_spec(plan_json: dict[str, Any]) -> dict[str, Any]:
    tool_name = ""
    for key in ("tool_name", "toolName", "name"):
        value = plan_json.get(key)
        if isinstance(value, str) and value.strip():
            tool_name = value.strip()
            break
    return {
        "tool_name": tool_name,
        "permissionLevel": 1,
        "permission_rationale": "Default least-privilege level for a generated read-only tool plan unless the approved capability requires more.",
        "validation_strategy": "core_sandbox_gate",
        "mvp_scope": [
            "Generate one Theseus custom tool as a BaseTool module.",
            "Validate compile/import/BaseTool subclass/required attributes/execute signature through Core sandbox gate.",
        ],
        "mvp_exclusions": [
            "Do not directly execute the generated Python file with python/python3.",
            "Do not use inline interpreter commands such as python -c.",
            "Do not use subprocess, os.system, shell execution, or arbitrary local program execution inside generated custom tool code.",
        ],
        "implementation_constraints": [
            "Import BaseTool, ToolExecutionContext, and ToolResult from theseus_engine.tools.core.base_tools.",
            "Define a Pydantic BaseModel input model and assign it to input_model.",
            "Define exactly one BaseTool subclass with name, description, input_model, permission_level, and async execute(arguments, context).",
            "Return ToolResult with JSON-serializable output.",
        ],
        "steps": [],
    }


def collect_execution_spec_quality_warnings(
    execution_spec: dict[str, Any],
    *,
    generated_tool_request: bool,
) -> list[str]:
    """Return non-blocking PLAN draft quality warnings."""

    warnings: list[str] = []
    strategy = str(execution_spec.get("validation_strategy") or "").strip()
    is_generated_sandbox_plan = generated_tool_request and strategy == "core_sandbox_gate"

    if generated_tool_request:
        permission_level = execution_spec.get("permissionLevel")
        if permission_level is None:
            permission_level = execution_spec.get("permission_level")
        if permission_level is None or str(permission_level).strip() == "":
            warnings.append(
                "품질 보완: generated tool execution_spec.permissionLevel을 1~5 정수로 명시하면 "
                "승인/생성 단계의 RBAC 판단이 명확해집니다."
            )

    mvp_exclusions = execution_spec.get("mvp_exclusions")
    if not isinstance(mvp_exclusions, list) or not mvp_exclusions:
        warnings.append("품질 보완: execution_spec.mvp_exclusions가 비어 있습니다.")

    outputs = execution_spec.get("outputs")
    required_fields: set[str] = set()
    if isinstance(outputs, dict):
        raw_fields = outputs.get("required_result_fields")
        if isinstance(raw_fields, list):
            required_fields = {str(item).strip() for item in raw_fields if str(item).strip()}
    missing_result_fields = {"evidence", "sanitized_output", "recommendation"} - required_fields
    if missing_result_fields:
        warnings.append(
            "품질 보완: execution_spec.outputs.required_result_fields에 "
            + ", ".join(sorted(missing_result_fields))
            + "를 포함하면 결과 검토성이 좋아집니다."
        )

    steps = execution_spec.get("steps")
    if steps is None:
        if not is_generated_sandbox_plan:
            warnings.append("품질 보완: execution_spec.steps가 없어 실행 단계가 덜 구체적입니다.")
        return warnings
    if not isinstance(steps, list):
        return warnings
    if not steps:
        if not is_generated_sandbox_plan:
            warnings.append("품질 보완: execution_spec.steps가 비어 있습니다.")
        return warnings

    for step_index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        commands = step.get("commands")
        if not isinstance(commands, list) or not commands:
            if not is_generated_sandbox_plan:
                warnings.append(f"품질 보완: steps[{step_index}]에 commands가 없습니다.")
        else:
            for command_index, command_spec in enumerate(commands, start=1):
                if not isinstance(command_spec, dict):
                    continue
                if not command_spec.get("failure_policy"):
                    warnings.append(
                        f"품질 보완: steps[{step_index}].commands[{command_index}].failure_policy가 없습니다."
                    )
                if not command_spec.get("parse_strategy"):
                    warnings.append(
                        f"품질 보완: steps[{step_index}].commands[{command_index}].parse_strategy가 없습니다."
                    )
        if not isinstance(step.get("json_mapping"), dict):
            warnings.append(f"품질 보완: steps[{step_index}]에 json_mapping이 없습니다.")
        decision_rules = step.get("decision_rules")
        if not isinstance(decision_rules, list) or not decision_rules:
            warnings.append(f"품질 보완: steps[{step_index}]에 decision_rules가 없습니다.")

    return warnings[:20]


def _validate_execution_spec_validation_strategy(
    execution_spec: dict[str, Any],
    generated_tool_request: bool,
    errors: list[str],
) -> None:
    strategy = str(execution_spec.get("validation_strategy") or "").strip()
    if not strategy:
        return
    if strategy != "core_sandbox_gate":
        errors.append("execution_spec.validation_strategy must be core_sandbox_gate when present.")
        return
    if not generated_tool_request:
        errors.append(
            "execution_spec.validation_strategy=core_sandbox_gate is only valid "
            "for generated Theseus custom tool plans."
        )


def _validate_execution_spec_shape(execution_spec: dict[str, Any], errors: list[str]) -> None:
    steps = execution_spec.get("steps")
    if steps is not None and not isinstance(steps, list):
        errors.append("execution_spec.steps must be a list when present.")

    status_values = execution_spec.get("status_values")
    if isinstance(status_values, list) and status_values:
        statuses = {str(item).strip().upper() for item in status_values}
        invalid = sorted(statuses - _ALLOWED_EXECUTION_STATUS_VALUES)
        if invalid:
            errors.append(f"execution_spec.status_values contains unsupported statuses: {invalid}.")


def _validate_execution_spec_command_policy(execution_spec: dict[str, Any], errors: list[str]) -> None:
    policy = execution_spec.get("command_policy")
    if policy is None:
        return
    if not isinstance(policy, dict):
        errors.append("execution_spec.command_policy must be an object when present.")
        return
    allowlist = policy.get("allowlist")
    denylist = policy.get("denylist")
    if allowlist is not None and not isinstance(allowlist, list):
        errors.append("execution_spec.command_policy.allowlist must be a list when present.")
    if denylist is not None and not isinstance(denylist, list):
        errors.append("execution_spec.command_policy.denylist must be a list when present.")


def _validate_execution_spec_api_checks(execution_spec: dict[str, Any], errors: list[str]) -> None:
    api_checks = execution_spec.get("api_checks")
    if api_checks in (None, []):
        return
    if not isinstance(api_checks, list):
        errors.append("execution_spec.api_checks must be a list when present.")
        return
    for index, check in enumerate(api_checks, start=1):
        if not isinstance(check, dict):
            errors.append(f"api_checks[{index}] must be an object.")
            continue
        method = str(check.get("method") or "").strip().upper()
        if method not in _READ_ONLY_API_METHODS:
            errors.append(
                f"api_checks[{index}] uses non-read-only method {method or '<missing>'}; "
                "MVP API checks allow only GET, HEAD, or OPTIONS."
            )
        if check.get("read_only") is not True:
            errors.append(f"api_checks[{index}].read_only must be true.")


def _validate_execution_spec_steps(execution_spec: dict[str, Any], errors: list[str]) -> None:
    steps = execution_spec.get("steps")
    if not isinstance(steps, list):
        return
    for step_index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            errors.append(f"steps[{step_index}] must be an object.")
            continue

        decision_rules = step.get("decision_rules")
        if isinstance(decision_rules, list):
            _validate_decision_rules(decision_rules, step_index, errors)

        commands = step.get("commands")
        if isinstance(commands, list):
            for command_index, command_spec in enumerate(commands, start=1):
                _validate_command_spec(command_spec, step_index, command_index, errors)


def _validate_decision_rules(
    decision_rules: list[Any],
    step_index: int,
    errors: list[str],
) -> None:
    if not decision_rules:
        return
    for rule_index, rule in enumerate(decision_rules, start=1):
        if not isinstance(rule, dict):
            errors.append(f"steps[{step_index}].decision_rules[{rule_index}] must be an object.")
            continue
        status = str(rule.get("status") or "").strip().upper()
        if status not in _ALLOWED_EXECUTION_STATUS_VALUES:
            errors.append(
                f"steps[{step_index}].decision_rules[{rule_index}] has unsupported status "
                f"{status or '<missing>'}."
            )
        condition = str(rule.get("condition") or "").strip().lower()
        if "health" in condition and "none" in condition and status == "FAIL":
            errors.append(
                f"steps[{step_index}].decision_rules[{rule_index}] treats Docker health none as FAIL; "
                "use SKIPPED or INFO."
            )
        if "healthcheck" in condition and "not configured" in condition and status == "FAIL":
            errors.append(
                f"steps[{step_index}].decision_rules[{rule_index}] treats missing healthcheck as FAIL; "
                "use SKIPPED or INFO."
            )


def _validate_command_spec(
    command_spec: Any,
    step_index: int,
    command_index: int,
    errors: list[str],
) -> None:
    if not isinstance(command_spec, dict):
        errors.append(f"steps[{step_index}].commands[{command_index}] must be an object.")
        return
    command = str(command_spec.get("command") or "").strip()
    if not command:
        return

    command_type = str(command_spec.get("type") or "").strip().lower()
    if command_type not in {"", "read_only"}:
        errors.append(f"steps[{step_index}].commands[{command_index}].type must be read_only.")

    _validate_command_text(command, step_index, command_index, command_spec, errors)


def _validate_command_text(
    command: str,
    step_index: int,
    command_index: int,
    command_spec: dict[str, Any],
    errors: list[str],
) -> None:
    lowered = command.lower()
    for pattern in _DENIED_COMMAND_PATTERNS:
        if re.search(pattern, lowered):
            errors.append(
                f"steps[{step_index}].commands[{command_index}] uses denied command pattern: {pattern}."
            )

    if "$(" in command or "`" in command:
        errors.append(f"steps[{step_index}].commands[{command_index}] uses command substitution.")
    without_stderr_redirect = lowered.replace("2>&1", "")
    if ">" in without_stderr_redirect:
        errors.append(f"steps[{step_index}].commands[{command_index}] uses output redirection.")
    if "&&" in lowered or ";" in lowered:
        errors.append(f"steps[{step_index}].commands[{command_index}] uses shell chaining.")
    if "||" in lowered and "|| true" not in lowered:
        errors.append(
            f"steps[{step_index}].commands[{command_index}] uses unsupported shell fallback; "
            "only `|| true` is allowed for grep no-match handling."
        )

    for segment in _command_segments(command):
        root = _command_root(segment)
        if root not in _ALLOWED_COMMAND_ROOTS:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] command segment "
                f"`{segment}` is outside the read-only allowlist."
            )
            continue
        if root in _VERIFICATION_COMMAND_ROOTS:
            _validate_verification_command_segment(segment, root, step_index, command_index, errors)
            continue
        if root == "docker":
            _validate_docker_command_segment(segment, step_index, command_index, command, errors)
        if root == "sed" and " -n" not in f" {segment.lower()} ":
            errors.append(f"steps[{step_index}].commands[{command_index}] uses sed without -n.")
        if root == "curl":
            _validate_curl_command(segment, step_index, command_index, errors)

    failure_policy = str(command_spec.get("failure_policy") or "").strip().lower()
    if "grep" in lowered and ("docker logs" in lowered or "log" in lowered):
        if failure_policy != "ignore_no_match" and "|| true" not in lowered:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] log grep must use "
                "failure_policy=ignore_no_match or `|| true` so no matches are not treated as failure."
            )


def _command_segments(command: str) -> list[str]:
    normalized = re.sub(r"\|\|\s*true\s*$", "", command.strip(), flags=re.IGNORECASE)
    return [
        segment.strip()
        for segment in re.split(r"(?<!\|)\|(?!\|)", normalized)
        if segment.strip()
    ]


def _command_root(segment: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", segment)
    return match.group(1).lower() if match else ""


def _validate_verification_command_segment(
    segment: str,
    root: str,
    step_index: int,
    command_index: int,
    errors: list[str],
) -> None:
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError as exc:
        errors.append(
            f"steps[{step_index}].commands[{command_index}] has an invalid "
            f"verification command: {exc}."
        )
        return
    if not tokens:
        return

    if root in {"python", "python3"}:
        _validate_python_verification_command(tokens, step_index, command_index, errors)
        return
    if root == "node":
        _validate_node_verification_command(tokens, step_index, command_index, errors)
        return
    if root == "git":
        _validate_git_verification_command(tokens, step_index, command_index, errors)


def _validate_python_verification_command(
    tokens: list[str],
    step_index: int,
    command_index: int,
    errors: list[str],
) -> None:
    args = tokens[1:]
    if "-c" in args:
        errors.append(
            f"steps[{step_index}].commands[{command_index}] uses inline Python execution; "
            "only python -B -m py_compile <file.py> or python -m json.tool <file.json> "
            "is allowed as a verification command."
        )
        return
    no_bytecode = bool(args and args[0] == "-B")
    if no_bytecode:
        args = args[1:]
    if len(args) >= 3 and args[:2] == ["-m", "py_compile"]:
        if not no_bytecode:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] py_compile verification "
                "must use -B to avoid writing __pycache__ files."
            )
            return
        paths = args[2:]
        if not paths:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] py_compile requires at least one .py path."
            )
            return
        for path in paths:
            if not _is_safe_relative_path(path, ".py"):
                errors.append(
                    f"steps[{step_index}].commands[{command_index}] py_compile path "
                    f"`{path}` must be a workspace-relative .py path."
                )
        return
    if len(args) == 3 and args[:2] == ["-m", "json.tool"]:
        path = args[2]
        if not _is_safe_relative_path(path, ".json"):
            errors.append(
                f"steps[{step_index}].commands[{command_index}] json.tool path "
                f"`{path}` must be a workspace-relative .json path."
            )
        return
    errors.append(
        f"steps[{step_index}].commands[{command_index}] uses Python outside the "
        "verification allowlist. Direct script execution is not allowed."
    )


def _validate_node_verification_command(
    tokens: list[str],
    step_index: int,
    command_index: int,
    errors: list[str],
) -> None:
    args = tokens[1:]
    if len(args) == 2 and args[0] == "--check" and _is_safe_relative_path(args[1], ".js"):
        return
    errors.append(
        f"steps[{step_index}].commands[{command_index}] uses node outside the "
        "verification allowlist. Only node --check <file.js> is allowed."
    )


def _validate_git_verification_command(
    tokens: list[str],
    step_index: int,
    command_index: int,
    errors: list[str],
) -> None:
    if tokens == ["git", "diff", "--check"]:
        return
    errors.append(
        f"steps[{step_index}].commands[{command_index}] uses git outside the "
        "verification allowlist. Only git diff --check is allowed."
    )


def _validate_docker_command_segment(
    segment: str,
    step_index: int,
    command_index: int,
    full_command: str,
    errors: list[str],
) -> None:
    parts = re.split(r"\s+", segment.strip())
    subcommand = parts[1].lower() if len(parts) > 1 else ""
    if subcommand not in _ALLOWED_DOCKER_SUBCOMMANDS:
        errors.append(
            f"steps[{step_index}].commands[{command_index}] uses unsupported docker subcommand "
            f"{subcommand or '<missing>'}."
        )
    if subcommand == "inspect":
        if "grep" in full_command.lower():
            errors.append(
                f"steps[{step_index}].commands[{command_index}] must not infer Docker health "
                "by grepping raw inspect output."
            )
        missing = [field for field in _DOCKER_INSPECT_REQUIRED_FIELDS if field not in full_command]
        if missing:
            errors.append(
                f"steps[{step_index}].commands[{command_index}] docker inspect command "
                f"missing fields: {missing}."
            )


def _validate_curl_command(
    segment: str,
    step_index: int,
    command_index: int,
    errors: list[str],
) -> None:
    lowered = segment.lower()
    if re.search(r"(^|\s)-x\s*(post|put|patch|delete)\b", lowered) or re.search(
        r"--request\s+(post|put|patch|delete)\b",
        lowered,
    ):
        errors.append(
            f"steps[{step_index}].commands[{command_index}] uses a data-changing curl method."
        )


def _is_safe_relative_path(raw_path: str, suffix: str) -> bool:
    value = str(raw_path or "").strip()
    if not value or value.startswith("-"):
        return False
    if value.startswith(("~", "/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
        return False
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".."} for part in path.parts):
        return False
    return value.lower().endswith(suffix.lower())
