"""Automatic SKILL.md selection and prompt injection helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from theseus_engine.skills.registry import load_skill_registry
from theseus_engine.skills.types import SkillDefinition


@dataclass(frozen=True)
class SkillInjectionConfig:
    """Runtime limits for automatic skill prompt injection."""

    enabled: bool = True
    max_skills: int = 3
    max_total_chars: int = 12_000
    max_per_skill_chars: int = 5_000


@dataclass(frozen=True)
class SelectedSkill:
    """A skill selected for the current user turn."""

    skill: SkillDefinition
    score: int
    matched_terms: tuple[str, ...]

    def to_metadata(self) -> dict[str, object]:
        return {
            "name": self.skill.name,
            "description": self.skill.description,
            "path": self.skill.path,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
        }


_TOKEN_RE = re.compile(r"[A-Za-z0-9_가-힣][A-Za-z0-9_가-힣.-]*")


def apply_skill_injection(
    *,
    system_prompt: str,
    cwd: Path,
    user_prompt: str,
    mode: str | None = None,
    config: SkillInjectionConfig | None = None,
) -> tuple[str, list[SelectedSkill]]:
    """Append matching skill content to the system prompt for this turn."""
    config = config or SkillInjectionConfig()
    selected = select_relevant_skills(
        cwd=cwd,
        user_prompt=user_prompt,
        mode=mode,
        config=config,
    )
    if not selected:
        return system_prompt, []

    section = render_skill_context(selected, config=config)
    if not section:
        return system_prompt, []
    return f"{system_prompt}\n\n{section}", selected


def select_relevant_skills(
    *,
    cwd: Path,
    user_prompt: str,
    mode: str | None = None,
    config: SkillInjectionConfig | None = None,
) -> list[SelectedSkill]:
    """Select skills by deterministic trigger/name/keyword matching."""
    config = config or SkillInjectionConfig()
    if not config.enabled or not user_prompt.strip():
        return []

    registry = load_skill_registry(cwd)
    scored: list[SelectedSkill] = []
    for skill in registry.list_skills():
        score, matched_terms = _score_skill(skill, user_prompt, mode)
        if score > 0:
            scored.append(
                SelectedSkill(
                    skill=skill,
                    score=score,
                    matched_terms=tuple(matched_terms),
                )
            )

    scored.sort(key=lambda item: (-item.score, item.skill.name.lower()))
    return scored[: max(0, config.max_skills)]


def render_skill_context(
    selected: Iterable[SelectedSkill],
    *,
    config: SkillInjectionConfig | None = None,
) -> str:
    """Render selected skills into a bounded system-prompt section."""
    config = config or SkillInjectionConfig()
    if config.max_total_chars <= 0:
        return ""

    header = (
        "# Active Skills\n"
        "The following SKILL.md procedures were automatically selected for this "
        "turn. Follow them when relevant, while preserving all higher-priority "
        "system instructions and the user's request.\n"
    )
    chunks: list[str] = [header]
    remaining = config.max_total_chars - len(header)
    if remaining <= 0:
        return ""

    for item in selected:
        skill_text = _skill_body(item.skill).strip()
        if not skill_text:
            continue
        per_skill_limit = max(0, min(config.max_per_skill_chars, remaining))
        if per_skill_limit <= 0:
            break
        skill_text = _truncate(skill_text, per_skill_limit)
        chunk = (
            f"\n## {item.skill.name}\n"
            f"Description: {item.skill.description}\n"
            f"Source: {item.skill.path or item.skill.source}\n\n"
            f"{skill_text}\n"
        )
        if len(chunk) > remaining:
            chunk = _truncate(chunk, remaining)
        chunks.append(chunk)
        remaining -= len(chunk)
        if remaining <= 0:
            break

    rendered = "".join(chunks).rstrip()
    if rendered == header.rstrip():
        return ""
    return rendered


def _score_skill(
    skill: SkillDefinition,
    user_prompt: str,
    mode: str | None,
) -> tuple[int, list[str]]:
    metadata = skill.metadata or {}
    if not _mode_matches(metadata.get("modes"), mode):
        return 0, []

    prompt_normalized = _normalize(user_prompt)
    prompt_tokens = set(_tokens(user_prompt))
    matched: list[str] = []
    score = 0

    for trigger in _string_list(metadata.get("triggers")):
        if _phrase_matches(trigger, prompt_normalized, prompt_tokens):
            score += 100
            matched.append(trigger)

    if _phrase_matches(skill.name, prompt_normalized, prompt_tokens):
        score += 60
        matched.append(skill.name)

    for keyword in _string_list(metadata.get("keywords")):
        if _phrase_matches(keyword, prompt_normalized, prompt_tokens):
            score += 40
            matched.append(keyword)

    for token in _tokens(skill.description):
        if len(token) >= 3 and token in prompt_tokens:
            score += 8
            matched.append(token)

    return score, _dedupe(matched)


def _mode_matches(raw_modes: object, mode: str | None) -> bool:
    modes = {_normalize(item) for item in _string_list(raw_modes)}
    if not modes:
        return True
    if mode is None:
        return False
    normalized_mode = _normalize(mode)
    return normalized_mode in modes or normalized_mode.split("/")[-1] in modes


def _phrase_matches(
    phrase: str,
    prompt_normalized: str,
    prompt_tokens: set[str],
) -> bool:
    normalized = _normalize(phrase)
    if not normalized:
        return False
    if " " in normalized or "-" in normalized:
        return normalized in prompt_normalized
    return normalized in prompt_tokens


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _tokens(text: str) -> list[str]:
    return [_normalize(match.group(0)) for match in _TOKEN_RE.finditer(text)]


def _normalize(text: str) -> str:
    normalized = str(text).lower().replace("_", " ").replace("-", " ")
    return " ".join(normalized.strip().split())


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _normalize(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
    return result


def _skill_body(skill: SkillDefinition) -> str:
    return skill.body or skill.content


def _truncate(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    suffix = "\n[Skill truncated]"
    if limit <= len(suffix):
        return text[:limit]
    return text[: limit - len(suffix)].rstrip() + suffix
