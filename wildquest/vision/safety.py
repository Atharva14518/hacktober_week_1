"""Deterministic safety checks for image-verification targets."""

from __future__ import annotations

import re


class UnsafeVisionTarget(ValueError):
    pass


_EDIBILITY = re.compile(
    r"\b(edible|eat|eating|consume|food|poisonous|safe to (?:eat|taste)|"
    r"taste|forage|medicinal)\b",
    re.IGNORECASE,
)


def validate_vision_target(target: str) -> str:
    """Block any request that could identify plants/animals for consumption."""
    normalized = " ".join(target.split())
    if not normalized:
        raise UnsafeVisionTarget("vision target cannot be empty")
    if _EDIBILITY.search(normalized):
        raise UnsafeVisionTarget(
            "Wild Quest never identifies plants or animals for eating or tasting"
        )
    return normalized
