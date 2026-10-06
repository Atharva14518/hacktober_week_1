"""Pure-Python quest adaptation rules driven by offline context."""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict

from wildquest.place.context import OfflineContext
from wildquest.quests.models import Difficulty, Quest, QuestType, Requirement
from wildquest.safety.rules import SafetyGuard


class AdaptationAction(str, Enum):
    KEEP = "keep"
    SHORTEN = "shorten"
    EASE = "ease"
    SWAP = "swap"
    END = "end"


class AdaptationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    action: AdaptationAction
    original_quest_id: str
    selected_quest: Quest | None
    reasons: tuple[str, ...]


_STATIONARY = {
    QuestType.OBSERVE,
    QuestType.LISTEN,
    QuestType.FIND,
    QuestType.SILENCE,
    QuestType.BIRD,
}


class AdaptationEngine:
    def __init__(
        self, quests: dict[str, Quest], safety: SafetyGuard | None = None
    ) -> None:
        self.quests = quests
        self.safety = safety or SafetyGuard()

    def adapt(self, quest: Quest, context: OfflineContext) -> AdaptationDecision:
        reasons: list[str] = []
        if not context.daylight or context.daylight_remaining_min <= 10:
            return AdaptationDecision(
                action=AdaptationAction.END,
                original_quest_id=quest.id,
                selected_quest=None,
                reasons=("insufficient daylight; end quests and use the safe route back",),
            )

        selected = quest
        action = AdaptationAction.KEEP

        if context.rain and (
            Requirement.DRY in selected.requires
            or selected.type in {QuestType.MOVE, QuestType.PHOTO}
        ):
            replacement = self._replacement(context, exclude={selected.id})
            if replacement is None:
                return self._end(quest, "rain left no eligible low-risk quest")
            selected = replacement
            action = AdaptationAction.SWAP
            reasons.append("rain: swapped out a movement, photo, or dry-ground quest")

        if context.tired and (
            selected.difficulty is not Difficulty.EASY or selected.type is QuestType.MOVE
        ):
            replacement = self._replacement(context, exclude={selected.id})
            if replacement is None:
                return self._end(quest, "fatigue left no eligible easy quest")
            selected = replacement
            action = AdaptationAction.SWAP
            reasons.append("fatigue: swapped to an easy stationary quest")
        elif context.tired:
            selected = selected.model_copy(
                update={"duration_min": max(1, min(3, selected.duration_min - 1))}
            )
            action = AdaptationAction.EASE
            reasons.append("fatigue: eased and shortened the quest")

        if context.daylight_remaining_min <= 45:
            if selected.type in {QuestType.MOVE, QuestType.PHOTO}:
                replacement = self._replacement(context, exclude={selected.id})
                if replacement is None:
                    return self._end(quest, "low daylight left no stationary quest")
                selected = replacement
                action = AdaptationAction.SWAP
                reasons.append("low daylight: swapped to a stationary quest")
            shortened = max(1, min(selected.duration_min, 3))
            if shortened < selected.duration_min:
                selected = selected.model_copy(update={"duration_min": shortened})
                if action is AdaptationAction.KEEP:
                    action = AdaptationAction.SHORTEN
                reasons.append("low daylight: limited duration to three minutes")

        if context.slow and selected.type is QuestType.MOVE:
            shortened = max(1, math.ceil(selected.duration_min * 0.6))
            selected = selected.model_copy(update={"duration_min": shortened})
            if action is AdaptationAction.KEEP:
                action = AdaptationAction.SHORTEN
            reasons.append("slow pace: reduced movement duration")

        if not self.safety.evaluate(selected, context.quest_context()).allowed:
            replacement = self._replacement(context, exclude={selected.id})
            if replacement is None:
                return self._end(quest, "safety filter found no eligible quest")
            selected = replacement
            action = AdaptationAction.SWAP
            reasons.append("safety filter: swapped to an eligible quest")

        return AdaptationDecision(
            action=action,
            original_quest_id=quest.id,
            selected_quest=selected,
            reasons=tuple(reasons) or ("conditions allow the original quest",),
        )

    def _replacement(
        self, context: OfflineContext, exclude: set[str]
    ) -> Quest | None:
        candidates = sorted(
            (
                candidate
                for candidate in self.quests.values()
                if candidate.id not in exclude
                and candidate.type in _STATIONARY
                and candidate.difficulty is Difficulty.EASY
                and self.safety.evaluate(candidate, context.quest_context()).allowed
            ),
            key=lambda candidate: (candidate.duration_min, candidate.id),
        )
        return candidates[0] if candidates else None

    @staticmethod
    def _end(quest: Quest, reason: str) -> AdaptationDecision:
        return AdaptationDecision(
            action=AdaptationAction.END,
            original_quest_id=quest.id,
            selected_quest=None,
            reasons=(reason,),
        )
