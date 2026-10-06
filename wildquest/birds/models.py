"""Strict data models for bird detections and quest goals."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BirdGoal(str, Enum):
    TARGET = "target"
    ANY_NEW_SPECIES = "any_new_species"


class BirdDetection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    label: str = Field(min_length=3, max_length=180)
    scientific_name: str = Field(min_length=2, max_length=100)
    common_name: str = Field(min_length=2, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def valid_times(self) -> BirdDetection:
        if self.end_s <= self.start_s:
            raise ValueError("detection end must follow its start")
        return self


class BirdAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    audio_path: str = Field(min_length=1, max_length=1000)
    audio_duration_s: float = Field(gt=0.0, le=60.0)
    inference_s: float = Field(ge=0.0)
    threshold: float = Field(ge=0.0, le=1.0)
    detections: tuple[BirdDetection, ...]


class BirdQuestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quest_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    goal: BirdGoal
    target_label: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def target_matches_goal(self) -> BirdQuestSpec:
        if self.goal is BirdGoal.TARGET and not self.target_label:
            raise ValueError("a target goal requires target_label")
        if self.goal is BirdGoal.ANY_NEW_SPECIES and self.target_label is not None:
            raise ValueError("an any-new-species goal cannot have target_label")
        return self


class BirdVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    passed: bool
    reason: str = Field(min_length=1, max_length=200)
    matched: BirdDetection | None = None


def load_bird_quest_specs(path: Path) -> dict[str, BirdQuestSpec]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("bird quest config must contain a list")
    specs: dict[str, BirdQuestSpec] = {}
    for item in raw:
        spec = BirdQuestSpec.model_validate(item)
        if spec.quest_id in specs:
            raise ValueError(f"duplicate bird quest spec {spec.quest_id!r}")
        specs[spec.quest_id] = spec
    if not specs:
        raise ValueError("bird quest config is empty")
    return specs
