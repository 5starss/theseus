"""Skill data models for Theseus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class SkillDefinition:
    """A defined skill recipe/methodology."""

    name: str
    description: str
    content: str
    source: str = "user"
    path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""
