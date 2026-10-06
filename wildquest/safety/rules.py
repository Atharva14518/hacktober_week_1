"""Deterministic outdoor safety gates and narration override."""

from __future__ import annotations

import re
from dataclasses import dataclass

from wildquest.quests.models import PlaceContext, Quest, Requirement


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


_REQUIREMENT_FIELDS: dict[Requirement, str] = {
    Requirement.DAYLIGHT: "daylight",
    Requirement.DRY: "dry",
    Requirement.MARKED_TRAIL: "on_marked_trail",
    Requirement.GOOD_VISIBILITY: "good_visibility",
    Requirement.LOW_WIND: "low_wind",
    Requirement.QUIET: "quiet",
    Requirement.LEVEL_GROUND: "level_ground",
    Requirement.WIDE_TRAIL: "wide_trail",
}

_UNSAFE_NARRATION = re.compile(
    r"\b(off[- ]?trail|leave (?:the )?(?:path|trail)|cliff edge|ledge|"
    r"enter (?:the )?water|wade|swim|touch (?:the )?(?:plant|animal|wildlife)|"
    r"eat (?:the )?(?:plant|berry|mushroom)|after dark|night hike)\b",
    re.IGNORECASE,
)


class SafetyGuard:
    def evaluate(self, quest: Quest, context: PlaceContext) -> SafetyDecision:
        reasons: list[str] = []
        if not context.daylight:
            reasons.append("quests are disabled after dark")
        if not context.on_marked_trail:
            reasons.append("return to a marked trail before continuing")
        if context.near_edge:
            reasons.append("move away from the edge before continuing")
        if context.near_water:
            reasons.append("move away from the water before continuing")
        for requirement in quest.requires:
            field = _REQUIREMENT_FIELDS[requirement]
            if not getattr(context, field):
                reasons.append(f"requires {requirement.value}")
        return SafetyDecision(not reasons, tuple(dict.fromkeys(reasons)))

    def safe_narration(self, narration: str, quest: Quest) -> str:
        """Override unsafe model prose in code, independent of its prompt."""
        if _UNSAFE_NARRATION.search(narration):
            return (
                f"Stay on the marked trail in daylight. {quest.prompt_seed} "
                "Skip this quest if the ground or surroundings feel unsafe."
            )
        return narration.strip()

