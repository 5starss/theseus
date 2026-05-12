"""Skill management tools for Theseus."""

from __future__ import annotations

import logging
import yaml
from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.skills.registry import load_skill_registry, ensure_skills_dir

log = logging.getLogger(__name__)


class SkillReadInput(BaseModel):
    """Input for reading a skill."""

    name: str = Field(description="Name of the skill to read")


class SkillReadTool(BaseTool):
    """Read a saved skill (recipe/methodology) by name."""

    name = "skill_read"
    description = "Read a saved skill (recipe, workflow, or methodology) to reuse past knowledge."
    input_model = SkillReadInput
    permission_level = 1

    async def execute(
        self, arguments: SkillReadInput, context: ToolExecutionContext
    ) -> ToolResult:
        registry = load_skill_registry(context.cwd)
        skill = registry.get(arguments.name)
        if not skill:
            return ToolResult(output=f"Skill not found: {arguments.name}", is_error=True)
        
        return ToolResult(output=f"--- SKILL: {skill.name} ---\n{skill.content}")


class SkillSaveInput(BaseModel):
    """Input for saving a new skill."""

    name: str = Field(description="Short name of the skill (e.g. 'react-setup')")
    description: str = Field(description="Brief description of what this skill does")
    content: str = Field(description="The full methodology or recipe in Markdown format")
    triggers: list[str] = Field(
        default_factory=list,
        description="Optional phrases that should activate this skill automatically",
    )


class SkillSaveTool(BaseTool):
    """Save a new skill (recipe/methodology) for future reuse."""

    name = "skill_save"
    description = "Save a new skill, workflow, or methodology as a markdown file for future reuse."
    input_model = SkillSaveInput
    permission_level = 2

    async def execute(
        self, arguments: SkillSaveInput, context: ToolExecutionContext
    ) -> ToolResult:
        skills_dir = ensure_skills_dir(context.cwd)  # 쓰기 시에만 디렉터리 생성
        # Normalize folder name
        folder_name = arguments.name.lower().replace(" ", "-")
        skill_folder = skills_dir / folder_name
        skill_folder.mkdir(parents=True, exist_ok=True)
        
        skill_file = skill_folder / "SKILL.md"
        
        metadata = {
            "name": arguments.name,
            "description": arguments.description,
        }
        if arguments.triggers:
            metadata["triggers"] = arguments.triggers
        frontmatter = yaml.safe_dump(
            metadata,
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        markdown_content = (
            f"---\n"
            f"{frontmatter}\n"
            f"---\n\n"
            f"{arguments.content}"
        )
        
        try:
            skill_file.write_text(markdown_content, encoding="utf-8")
            return ToolResult(
                output=f"✅ Skill saved: {arguments.name}\nPath: {skill_file}"
            )
        except Exception as exc:
            return ToolResult(output=f"Skill save failed: {exc}", is_error=True)


class SkillListInput(BaseModel):
    """Input for listing skills."""


class SkillListTool(BaseTool):
    """List all available skills."""

    name = "skill_list"
    description = "List all saved skills and methodologies."
    input_model = SkillListInput
    permission_level = 1

    async def execute(
        self, arguments: SkillListInput, context: ToolExecutionContext
    ) -> ToolResult:
        registry = load_skill_registry(context.cwd)
        skills = registry.list_skills()
        if not skills:
            return ToolResult(output="(No saved skills)")
        
        lines = [
            f"- {s.name}: {s.description}"
            for s in skills
        ]
        return ToolResult(output="\n".join(lines))
