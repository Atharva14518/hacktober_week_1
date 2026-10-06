"""Validated quest definitions and runtime context."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestType(str, Enum):
    OBSERVE = "observe"
    LISTEN = "listen"
    FIND = "find"
    MOVE = "move"
    SILENCE = "silence"
    BIRD = "bird"
    PHOTO = "photo"


class Difficulty(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    CHALLENGING = "challenging"


class Requirement(str, Enum):
    DAYLIGHT = "daylight"
    DRY = "dry"
    MARKED_TRAIL = "marked_trail"
    GOOD_VISIBILITY = "good_visibility"
    LOW_WIND = "low_wind"
    QUIET = "quiet"
    LEVEL_GROUND = "level_ground"
    WIDE_TRAIL = "wide_trail"


class Quest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    type: QuestType
    difficulty: Difficulty
    duration_min: int = Field(ge=1, le=30)
    requires: tuple[Requirement, ...]
    prompt_seed: str = Field(min_length=12, max_length=500)
    success_criteria: str = Field(min_length=8, max_length=300)
    hint: str = Field(min_length=5, max_length=300)
    safety_notes: str = Field(min_length=8, max_length=400)

    @field_validator("requires")
    @classmethod
    def unique_requirements(
        cls, requirements: tuple[Requirement, ...]
    ) -> tuple[Requirement, ...]:
        if len(requirements) != len(set(requirements)):
            raise ValueError("quest requirements must be unique")
        return requirements


class PlaceContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    place_name: str = Field(min_length=1, max_length=120)
    daylight: bool
    dry: bool
    on_marked_trail: bool
    good_visibility: bool = True
    low_wind: bool = True
    quiet: bool = True
    level_ground: bool = True
    wide_trail: bool = True
    near_edge: bool = False
    near_water: bool = False
    weather_note: str = Field(default="clear", max_length=120)


def load_quests(directory: Path) -> dict[str, Quest]:
    """Load one safely parsed, strictly validated quest per YAML file."""
    quests: dict[str, Quest] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        quest = Quest.model_validate(raw)
        if quest.id in quests:
            raise ValueError(f"duplicate quest id {quest.id!r} in {path}")
        quests[quest.id] = quest
    if not quests:
        raise ValueError(f"no quests found in {directory}")
    return quests
