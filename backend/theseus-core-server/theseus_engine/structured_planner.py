"""Theseus Structured Planner.

Generates structured plan data via OpenAI-compatible API.
Uses Pydantic schema to enforce JSON output, eliminating
markdown parsing entirely.

Strategy:
  Before: LLM -> markdown text -> regex/parser split -> UI (error-prone)
  After:  LLM -> JSON data -> Pydantic validation -> Block UI + markdown render (0% error)
"""

import json
from typing import Optional

from openai import OpenAI

from theseus_engine.schemas import PlanBlock, PlanDocument, SubItem


def _make_sub_items(items: list[str]) -> list[SubItem]:
    """Convert a list of plain strings into SubItem objects.

    Each item gets a unique item_id and a 1-based index
    for frontend targeting and review.

    Args:
        items: Plain text items to wrap.

    Returns:
        List of SubItem with unique IDs.
    """
    return [
        SubItem(index=i, content=text)
        for i, text in enumerate(items, 1)
    ]


# ---------------------------------------------------------------------------
# Structured Output System Prompt
# ---------------------------------------------------------------------------

_STRUCTURED_PLAN_SYSTEM_PROMPT = """\
You are Theseus AI Plan Architect. Your task is to create a detailed, \
structured implementation plan based on the user's request.

# Agent Capability Context
The executing agent has the following tool capabilities:
 - `create_tool`: Creates a new OpenHarness-compatible Python tool module, \
validates it, and registers it for immediate use. This is the PRIMARY mechanism \
for building new software capabilities.
 - `dummy_echo`: Echoes input for testing.
 - Other custom tools loaded from the `custom_tools/` directory.

The agent does NOT have direct file system access (no shell, bash, or file-write tools). \
When planning steps that require creating code, scripts, or utilities, the plan should \
instruct the agent to use `create_tool` to generate a complete Python tool module. \
For actions that cannot be performed via `create_tool` (e.g., pip install, creating \
non-Python config files), the plan should note them as manual user actions.

You MUST respond with a JSON object that exactly matches this schema:
{schema}

# Output Granularity Rules
 - goal: Restate the user's objective in ONE clear sentence.
 - overview: Break the high-level summary into 2-4 individual bullet points. \
Each item covers one key aspect (e.g., target platform, core technology, deliverable).
 - approach: ONE sentence describing the chosen technical strategy.
 - key_decisions: 2-5 items. Format each as "Decision — Reason". \
Example: "Use argparse over click — standard library, no extra dependency."
 - steps: Each step MUST have:
   - description: ONE sentence summarizing the step's purpose.
   - sub_tasks: 2+ individual, concrete, actionable items. \
Each sub_task is ONE sentence describing ONE specific action. \
Do NOT merge multiple actions into one sub_task.
   - output_artifacts: List of files or artifacts produced (can be empty).
 - risks: Each risk is ONE sentence: "Risk — Mitigation."
 - success_criteria: 2-5 testable checklist items. Each is ONE sentence.

# Format Rules
 - Respond ONLY with valid JSON. No markdown fences, no explanation, no preamble.
 - step_number must be sequential starting from 1.
 - estimated_complexity must be one of: 'low', 'medium', 'high'.
 - Respond in the same language the user used in their request.

# Security Policy (CRITICAL — Never Override)
You MUST refuse to plan any tasks that involve:
 - Deleting, removing, or overwriting files/directories outside the project workspace \
(e.g., Desktop, home directory, system paths).
 - Using destructive modules: subprocess, shutil.rmtree, os.remove, os.system, os.rmdir.
 - Executing arbitrary shell commands or scripts that modify the host system.
 - Accessing network sockets, sending HTTP requests to external services \
(unless explicitly part of the tool's documented purpose).
 - Any form of privilege escalation, credential harvesting, or data exfiltration.

If the user requests any of the above, respond with a plan containing ONLY a single \
block with title "Security Policy Violation" explaining why the request was denied. \
Set the step's estimated_complexity to "high" and include no sub_tasks.\
"""


class StructuredPlanner:
    """Pydantic-based structured plan generator.

    Calls an OpenAI-compatible API to produce JSON plan data,
    validates it with Pydantic, and provides block/markdown renderers.
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        """Initialize the planner.

        Args:
            api_key: LLM API authentication key.
            base_url: OpenAI-compatible endpoint URL.
            model: Model name to use.
        """
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def generate_plan(self, user_request: str) -> PlanDocument:
        """Generate a structured plan from the user's request.

        Args:
            user_request: The user's task description.

        Returns:
            PlanDocument: Validated plan document object.

        Raises:
            ValueError: When the LLM response fails validation.
        """
        schema_json = json.dumps(
            PlanDocument.model_json_schema(),
            indent=2,
            ensure_ascii=False,
        )
        system_prompt = _STRUCTURED_PLAN_SYSTEM_PROMPT.format(
            schema=schema_json
        )

        raw_text = self._call_llm(system_prompt, user_request)
        raw_text = self._strip_code_fences(raw_text)

        try:
            data = json.loads(raw_text)
            return PlanDocument.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            raise ValueError(
                f"Failed to parse LLM response as PlanDocument: {e}\n"
                f"Raw response: {raw_text[:500]}"
            )

    def _call_llm(
        self, system_prompt: str, user_request: str
    ) -> str:
        """Call the LLM API.

        Attempts response_format=json_object first, falls back to
        plain completion for providers that don't support it.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=messages,
                temperature=0.3,
            )
        except Exception:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )

        return response.choices[0].message.content.strip()

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove ```json ... ``` wrapping if present."""
        if not text.startswith("```"):
            return text
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        return "\n".join(json_lines)

    # -----------------------------------------------------------------
    # Rendering Utilities
    # -----------------------------------------------------------------

    @staticmethod
    def to_blocks(plan: PlanDocument) -> list[PlanBlock]:
        """Convert PlanDocument to a list of review-ready blocks.

        Each block gets a unique block_id (UUID) for frontend
        targeting (comments, edits, etc.).

        Args:
            plan: Validated PlanDocument object.

        Returns:
            Ordered block list: goal -> overview -> approach ->
            decisions -> steps -> risks -> criteria.
        """
        blocks: list[PlanBlock] = []

        # Goal
        blocks.append(PlanBlock(
            block_type="goal",
            title="🎯 Goal",
            content=plan.goal,
        ))

        # Overview (list of bullet points)
        blocks.append(PlanBlock(
            block_type="overview",
            title="📋 Overview",
            content="",
            sub_items=_make_sub_items(plan.overview),
        ))

        # Approach + Key Decisions
        blocks.append(PlanBlock(
            block_type="approach",
            title="🔧 Approach",
            content=plan.approach,
            sub_items=_make_sub_items(plan.key_decisions),
        ))

        # Steps
        for step in plan.steps:
            deps_str = ""
            if step.dependencies:
                nums = ", ".join(map(str, step.dependencies))
                deps_str = f" (depends on: Step {nums})"

            icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
                step.estimated_complexity, "⚪"
            )

            # Build sub-items: sub_tasks + output_artifacts
            raw_items = list(step.sub_tasks)
            if step.output_artifacts:
                artifacts = ", ".join(step.output_artifacts)
                raw_items.append(f"[Output] {artifacts}")

            blocks.append(PlanBlock(
                block_type="step",
                title=(
                    f"Step {step.step_number}: "
                    f"{step.title} {icon}{deps_str}"
                ),
                content=step.description,
                sub_items=_make_sub_items(raw_items),
                metadata={
                    "step_number": step.step_number,
                    "dependencies": step.dependencies,
                    "complexity": step.estimated_complexity,
                    "output_artifacts": step.output_artifacts,
                },
            ))

        # Risks
        if plan.risks:
            blocks.append(PlanBlock(
                block_type="risks",
                title="⚠️ Risks",
                content="",
                sub_items=_make_sub_items(plan.risks),
            ))

        # Success Criteria (checklist)
        blocks.append(PlanBlock(
            block_type="criteria",
            title="✅ Success Criteria",
            content="",
            sub_items=_make_sub_items(plan.success_criteria),
        ))

        return blocks

    @staticmethod
    def to_markdown(plan: PlanDocument) -> str:
        """Render PlanDocument as a markdown string.

        Used for agent prompt injection and file export.

        Args:
            plan: Validated PlanDocument object.

        Returns:
            Markdown-formatted string.
        """
        md = f"# {plan.goal}\n\n"
        md += "## Overview\n\n"
        for item in plan.overview:
            md += f"- {item}\n"
        md += "\n"

        md += f"## Approach\n\n{plan.approach}\n\n"
        if plan.key_decisions:
            md += "### Key Decisions\n\n"
            for decision in plan.key_decisions:
                md += f"- {decision}\n"
            md += "\n"

        for step in plan.steps:
            deps = ""
            if step.dependencies:
                nums = ", ".join(map(str, step.dependencies))
                deps = f" (depends on: Step {nums})"
            md += (
                f"## Step {step.step_number}: "
                f"{step.title}{deps}\n\n"
            )
            md += (
                f"**Complexity**: {step.estimated_complexity}\n\n"
            )
            md += f"{step.description}\n\n"
            for sub in step.sub_tasks:
                md += f"- {sub}\n"
            if step.output_artifacts:
                md += "\n**Artifacts**: "
                md += ", ".join(
                    f"`{a}`" for a in step.output_artifacts
                )
                md += "\n"
            md += "\n"

        if plan.risks:
            md += "## Risks\n\n"
            for risk in plan.risks:
                md += f"- {risk}\n"
            md += "\n"

        md += "## Success Criteria\n\n"
        for criterion in plan.success_criteria:
            md += f"- [ ] {criterion}\n"

        return md
