"""Deterministic quest state machine. The LLM has no completion authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from wildquest.core.store import PlayerProgress, QuestStore, StoredRun
from wildquest.quests.models import Difficulty, PlaceContext, Quest
from wildquest.safety.rules import SafetyGuard


class QuestState(str, Enum):
    IDLE = "idle"
    OFFERED = "offered"
    ACTIVE = "active"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ENDED = "ended"


class TransitionError(RuntimeError):
    pass


class VerificationEvidence(BaseModel):
    """Evidence from deterministic application code, never an LLM response."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    passed: bool
    source: str = Field(pattern=r"^(timer|sensor|photo_metadata|user_confirmation)$")
    detail: str = Field(min_length=1, max_length=200)


@dataclass(frozen=True)
class EngineSnapshot:
    state: QuestState
    quest: Quest | None
    progress: PlayerProgress
    persona: str | None


_XP: dict[Difficulty, int] = {
    Difficulty.EASY: 10,
    Difficulty.MODERATE: 20,
    Difficulty.CHALLENGING: 30,
}

_ALLOWED: dict[QuestState, frozenset[QuestState]] = {
    QuestState.OFFERED: frozenset(
        {QuestState.ACTIVE, QuestState.SKIPPED, QuestState.ENDED}
    ),
    QuestState.ACTIVE: frozenset(
        {QuestState.VERIFYING, QuestState.SKIPPED, QuestState.ENDED}
    ),
    QuestState.VERIFYING: frozenset(
        {QuestState.ACTIVE, QuestState.COMPLETED, QuestState.SKIPPED, QuestState.ENDED}
    ),
}


class QuestEngine:
    def __init__(
        self,
        quests: dict[str, Quest],
        store: QuestStore,
        safety: SafetyGuard | None = None,
    ) -> None:
        self.quests = quests
        self.store = store
        self.safety = safety or SafetyGuard()

    def snapshot(self) -> EngineSnapshot:
        run = self.store.current_run()
        if run is None:
            return EngineSnapshot(QuestState.IDLE, None, self.store.progress(), None)
        quest = self.quests.get(run.quest_id)
        if quest is None:
            raise RuntimeError(f"persisted quest {run.quest_id!r} is not in catalog")
        return EngineSnapshot(
            QuestState(run.state), quest, self.store.progress(), run.persona
        )

    def offer(self, quest_id: str, context: PlaceContext, persona: str) -> EngineSnapshot:
        snapshot = self.snapshot()
        if snapshot.state not in {
            QuestState.IDLE,
            QuestState.COMPLETED,
            QuestState.SKIPPED,
            QuestState.ENDED,
        }:
            raise TransitionError(f"cannot offer from {snapshot.state.value}")
        quest = self.quests[quest_id]
        decision = self.safety.evaluate(quest, context)
        if not decision.allowed:
            raise TransitionError("unsafe quest: " + "; ".join(decision.reasons))
        self.store.create_run(quest_id, persona)
        return self.snapshot()

    def offer_next(self, context: PlaceContext, persona: str) -> EngineSnapshot:
        completed = self.store.completed_quest_ids()
        for quest in self.quests.values():
            if quest.id not in completed and self.safety.evaluate(quest, context).allowed:
                return self.offer(quest.id, context, persona)
        raise TransitionError("no safe, unfinished quest is available")

    def accept(self) -> EngineSnapshot:
        self._transition(QuestState.ACTIVE, "user accepted quest")
        return self.snapshot()

    def request_verification(self) -> EngineSnapshot:
        self._transition(QuestState.VERIFYING, "user reported done")
        return self.snapshot()

    def verify(self, evidence: VerificationEvidence) -> EngineSnapshot:
        run, quest = self._current()
        if QuestState(run.state) is not QuestState.VERIFYING:
            raise TransitionError("verification requires verifying state")
        if evidence.passed:
            progress = self.store.progress()
            streak_bonus = min(progress.streak, 5) * 2
            award = _XP[quest.difficulty] + streak_bonus
            self.store.transition(
                run,
                QuestState.COMPLETED.value,
                f"verified by {evidence.source}: {evidence.detail}",
                xp_award=award,
                completed=True,
            )
        else:
            self.store.transition(
                run,
                QuestState.ACTIVE.value,
                f"verification failed: {evidence.detail}",
            )
        return self.snapshot()

    def skip(self) -> EngineSnapshot:
        self._transition(QuestState.SKIPPED, "user skipped quest", reset_streak=True)
        return self.snapshot()

    def end(self, reason: str = "user ended session") -> EngineSnapshot:
        self._transition(QuestState.ENDED, reason, reset_streak=True)
        return self.snapshot()

    def _current(self) -> tuple[StoredRun, Quest]:
        run = self.store.current_run()
        if run is None:
            raise TransitionError("no current quest")
        return run, self.quests[run.quest_id]

    def _transition(
        self, to_state: QuestState, reason: str, *, reset_streak: bool = False
    ) -> StoredRun:
        run, _ = self._current()
        from_state = QuestState(run.state)
        if to_state not in _ALLOWED.get(from_state, frozenset()):
            raise TransitionError(
                f"invalid transition {from_state.value} -> {to_state.value}"
            )
        return self.store.transition(
            run, to_state.value, reason, reset_streak=reset_streak
        )

