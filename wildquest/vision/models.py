"""Strict models for photo-quest inference and deterministic gating."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class VisionAnswer(BaseModel):
    """The only model output accepted by vision logic."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    answer: Literal["yes", "no"]
    confidence: float = Field(ge=0.0, le=1.0)


class VisionAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    image_path: str = Field(min_length=1, max_length=1000)
    target: str = Field(min_length=1, max_length=160)
    model: str = Field(min_length=1, max_length=100)
    answer: VisionAnswer
    first_token_s: float = Field(ge=0.0)
    total_s: float = Field(ge=0.0)
    parse_valid: bool
    attempts: int = Field(ge=1, le=2)
    error: str | None = Field(default=None, max_length=300)


class VisionQuestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quest_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    target: str = Field(min_length=1, max_length=160)
    confidence_threshold: float = Field(default=0.80, ge=0.5, le=1.0)


class VisionVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    passed: bool
    reason: str = Field(min_length=1, max_length=200)


def load_vision_quest_specs(path: Path) -> dict[str, VisionQuestSpec]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("vision quest config must contain a list")
    specs: dict[str, VisionQuestSpec] = {}
    for item in raw:
        spec = VisionQuestSpec.model_validate(item)
        if spec.quest_id in specs:
            raise ValueError(f"duplicate vision quest spec {spec.quest_id!r}")
        specs[spec.quest_id] = spec
    if not specs:
        raise ValueError("vision quest config is empty")
    return specs
