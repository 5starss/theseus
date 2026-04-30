"""Skill registry and loader for Theseus."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Iterable

import yaml
from theseus_engine.skills.types import SkillDefinition

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Store and manage loaded skills."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.name.lower()] = skill

    def get(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name.lower())

    def list_skills(self) -> List[SkillDefinition]:
        return sorted(self._skills.values(), key=lambda s: s.name)


def get_skills_dir(cwd: Path) -> Path:
    """Get the skills directory in the workspace."""
    path = cwd / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_skill_registry(cwd: Path) -> SkillRegistry:
    """Load all skills from the workspace."""
    registry = SkillRegistry()
    skills_dir = get_skills_dir(cwd)
    
    if not skills_dir.exists():
        return registry

    for skill_folder in sorted(skills_dir.iterdir()):
        if skill_folder.is_dir():
            skill_file = skill_folder / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    name, description = _parse_skill_markdown(skill_folder.name, content)
                    registry.register(
                        SkillDefinition(
                            name=name,
                            description=description,
                            content=content,
                            path=str(skill_file),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to load skill from {skill_folder}: {e}")
    
    return registry


def _parse_skill_markdown(default_name: str, content: str) -> tuple[str, str]:
    """Parse name and description from skill markdown."""
    name = default_name
    description = f"Skill: {name}"
    
    # Simple YAML frontmatter parsing
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            try:
                meta = yaml.safe_load(content[4:end])
                if isinstance(meta, dict):
                    name = meta.get("name", name)
                    description = meta.get("description", description)
            except Exception:
                pass

    return name, description
