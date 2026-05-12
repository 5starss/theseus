"""Skill registry and loader for Theseus."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    """스킬 디렉터리 경로를 반환합니다 (디렉터리 생성 없음)."""
    return cwd / "skills"


def ensure_skills_dir(cwd: Path) -> Path:
    """스킬 디렉터리가 없으면 생성 후 경로를 반환합니다."""
    path = get_skills_dir(cwd)
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
                    name, description, metadata, body = _parse_skill_markdown(
                        skill_folder.name,
                        content,
                    )
                    registry.register(
                        SkillDefinition(
                            name=name,
                            description=description,
                            content=content,
                            source=str(metadata.get("source", "user")),
                            path=str(skill_file),
                            metadata=metadata,
                            body=body,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to load skill from {skill_folder}: {e}")
    
    return registry


def _parse_skill_markdown(
    default_name: str,
    content: str,
) -> tuple[str, str, dict[str, Any], str]:
    """Parse name and description from skill markdown."""
    name = default_name
    description = f"Skill: {name}"

    metadata, body = _split_frontmatter(content)
    if metadata:
        name = str(metadata.get("name") or name)
        description = str(metadata.get("description") or description)
        for key in ("triggers", "keywords", "modes"):
            metadata[key] = _coerce_string_list(metadata.get(key))

    return name, description, metadata, body


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Return parsed YAML frontmatter and markdown body."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_index: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        return {}, content

    raw_meta = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    try:
        loaded = yaml.safe_load(raw_meta) or {}
    except Exception:
        return {}, body
    if not isinstance(loaded, dict):
        return {}, body
    return dict(loaded), body


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]
