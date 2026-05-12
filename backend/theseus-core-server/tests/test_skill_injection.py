import tempfile
import unittest
from pathlib import Path

from theseus_engine.engine.query_engine import QueryEngine
from theseus_engine.engine.stream_events import AssistantTurnComplete
from theseus_engine.models.messages import ConversationMessage, TextBlock
from theseus_engine.skills.injection import (
    SkillInjectionConfig,
    render_skill_context,
    select_relevant_skills,
)
from theseus_engine.skills.registry import load_skill_registry
from theseus_engine.tools.core.base_tools import ToolRegistry
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    UsageSnapshot,
)


class AllowAllPermissionChecker:
    def evaluate(self, *args, **kwargs):
        class Decision:
            allowed = True
            requires_confirmation = False
            reason = ""

        return Decision()


class CapturingClient:
    def __init__(self) -> None:
        self.requests = []

    async def stream_message(self, request):
        self.requests.append(request)
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(
                role="assistant",
                content=[TextBlock(text="done")],
            ),
            usage=UsageSnapshot(),
        )


def write_skill(
    root: Path,
    folder: str,
    *,
    name: str,
    description: str,
    body: str,
    triggers: list[str] | None = None,
    keywords: list[str] | None = None,
    modes: list[str] | None = None,
) -> None:
    skill_dir = root / "skills" / folder
    skill_dir.mkdir(parents=True)
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if triggers:
        lines.append("triggers:")
        lines.extend(f"  - {item}" for item in triggers)
    if keywords:
        lines.append("keywords:")
        lines.extend(f"  - {item}" for item in keywords)
    if modes:
        lines.append("modes:")
        lines.extend(f"  - {item}" for item in modes)
    lines.extend(["---", "", body])
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


class SkillInjectionTests(unittest.TestCase):
    def test_registry_parses_frontmatter_metadata_and_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(
                root,
                "pytest-flow",
                name="pytest-flow",
                description="Run focused pytest checks",
                triggers=["pytest"],
                keywords=["tests"],
                modes=["Agent"],
                body="Use pytest with the narrowest useful target.",
            )

            skill = load_skill_registry(root).get("pytest-flow")

            self.assertIsNotNone(skill)
            assert skill is not None
            self.assertEqual(skill.metadata["triggers"], ["pytest"])
            self.assertEqual(skill.metadata["keywords"], ["tests"])
            self.assertEqual(skill.metadata["modes"], ["Agent"])
            self.assertEqual(skill.body, "Use pytest with the narrowest useful target.")
            self.assertIn("name: pytest-flow", skill.content)

    def test_select_relevant_skills_uses_triggers_keywords_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(
                root,
                "pytest-flow",
                name="pytest-flow",
                description="Run focused pytest checks",
                triggers=["pytest"],
                keywords=["tests"],
                modes=["Agent"],
                body="Use pytest with the narrowest useful target.",
            )
            write_skill(
                root,
                "plan-review",
                name="plan-review",
                description="Review implementation plans",
                triggers=["roadmap"],
                modes=["Plan"],
                body="Review the plan before implementation.",
            )

            selected = select_relevant_skills(
                cwd=root,
                user_prompt="Run pytest for the skill injection tests",
                mode="Agent",
                config=SkillInjectionConfig(max_skills=3),
            )

            self.assertEqual([item.skill.name for item in selected], ["pytest-flow"])
            self.assertIn("pytest", selected[0].matched_terms)

    def test_render_skill_context_respects_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(
                root,
                "long-skill",
                name="long-skill",
                description="Long skill",
                triggers=["long"],
                body="x" * 200,
            )
            selected = select_relevant_skills(
                cwd=root,
                user_prompt="use long",
                config=SkillInjectionConfig(max_per_skill_chars=40),
            )

            rendered = render_skill_context(
                selected,
                config=SkillInjectionConfig(max_total_chars=500, max_per_skill_chars=40),
            )

            self.assertLessEqual(len(rendered), 500)
            self.assertIn("Active Skills", rendered)
            self.assertIn("Skill truncated", rendered)

    def test_missing_skills_dir_is_not_created_by_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            selected = select_relevant_skills(cwd=root, user_prompt="pytest")

            self.assertEqual(selected, [])
            self.assertFalse((root / "skills").exists())


class QueryEngineSkillInjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_message_injects_matching_skill_into_effective_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(
                root,
                "pytest-flow",
                name="pytest-flow",
                description="Run focused pytest checks",
                triggers=["pytest"],
                body="Use pytest with the narrowest useful target.",
            )
            client = CapturingClient()
            engine = QueryEngine(
                api_client=client,
                tool_registry=ToolRegistry(),
                permission_checker=AllowAllPermissionChecker(),
                cwd=root,
                model="test-model",
                system_prompt="Base prompt.",
                skill_injection_config=SkillInjectionConfig(),
                tool_metadata={"agent_mode": "Agent"},
            )

            events = [
                event async for event in engine.submit_message("Please run pytest now")
            ]

            self.assertTrue(any(isinstance(event, AssistantTurnComplete) for event in events))
            self.assertEqual(engine.system_prompt, "Base prompt.")
            self.assertIn("# Active Skills", client.requests[0].system_prompt)
            self.assertIn("pytest-flow", client.requests[0].system_prompt)
            self.assertIn(
                "Use pytest with the narrowest useful target.",
                client.requests[0].system_prompt,
            )
            self.assertEqual(engine.tool_metadata["active_skills"][0]["name"], "pytest-flow")
            self.assertNotIn(
                "Use pytest with the narrowest useful target.",
                "\n".join(message.text for message in engine.messages),
            )

    async def test_submit_message_skips_injection_when_config_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(
                root,
                "pytest-flow",
                name="pytest-flow",
                description="Run focused pytest checks",
                triggers=["pytest"],
                body="Use pytest with the narrowest useful target.",
            )
            client = CapturingClient()
            engine = QueryEngine(
                api_client=client,
                tool_registry=ToolRegistry(),
                permission_checker=AllowAllPermissionChecker(),
                cwd=root,
                model="test-model",
                system_prompt="Base prompt.",
                skill_injection_config=SkillInjectionConfig(enabled=False),
            )

            async for _ in engine.submit_message("Please run pytest now"):
                pass

            self.assertEqual(client.requests[0].system_prompt, "Base prompt.")
            self.assertEqual(engine.tool_metadata["active_skills"], [])


if __name__ == "__main__":
    unittest.main()
