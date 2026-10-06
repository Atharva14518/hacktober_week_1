from pathlib import Path

import pytest

from wildquest.core.store import QuestStore
from wildquest.quests.engine import (
    QuestEngine,
    QuestState,
    TransitionError,
    VerificationEvidence,
)
from wildquest.quests.models import PlaceContext, load_quests


QUESTS = load_quests(Path(__file__).parents[1] / "data/quests")


def context() -> PlaceContext:
    return PlaceContext(
        place_name="Test Trail",
        daylight=True,
        dry=True,
        on_marked_trail=True,
    )


def engine_at(tmp_path: Path) -> QuestEngine:
    return QuestEngine(QUESTS, QuestStore(tmp_path / "quest.db"))


def test_full_lifecycle_awards_xp_only_after_verification(tmp_path: Path) -> None:
    engine = engine_at(tmp_path)
    assert engine.snapshot().state is QuestState.IDLE
    assert engine.offer("three-colors", context(), "calm_naturalist").state is QuestState.OFFERED
    assert engine.accept().state is QuestState.ACTIVE
    verifying = engine.request_verification()
    assert verifying.state is QuestState.VERIFYING
    assert verifying.progress.xp == 0

    completed = engine.verify(
        VerificationEvidence(
            passed=True,
            source="user_confirmation",
            detail="three colors were named",
        )
    )
    assert completed.state is QuestState.COMPLETED
    assert completed.progress.xp == 10
    assert completed.progress.streak == 1


def test_failed_verification_returns_to_active_without_xp(tmp_path: Path) -> None:
    engine = engine_at(tmp_path)
    engine.offer("three-colors", context(), "epic_fantasy")
    engine.accept()
    engine.request_verification()
    result = engine.verify(
        VerificationEvidence(
            passed=False, source="timer", detail="timer had not elapsed"
        )
    )
    assert result.state is QuestState.ACTIVE
    assert result.progress.xp == 0


def test_resume_after_crash_restores_active_and_verifying_states(tmp_path: Path) -> None:
    database = tmp_path / "quest.db"
    first = QuestEngine(QUESTS, QuestStore(database))
    first.offer("sound-layers", context(), "local_guide")
    first.accept()

    restarted = QuestEngine(QUESTS, QuestStore(database))
    assert restarted.snapshot().state is QuestState.ACTIVE
    restarted.request_verification()

    restarted_again = QuestEngine(QUESTS, QuestStore(database))
    snapshot = restarted_again.snapshot()
    assert snapshot.state is QuestState.VERIFYING
    assert snapshot.quest is not None and snapshot.quest.id == "sound-layers"
    assert snapshot.persona == "local_guide"


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    engine = engine_at(tmp_path)
    engine.offer("three-colors", context(), "calm_naturalist")
    with pytest.raises(TransitionError):
        engine.request_verification()


def test_safety_can_override_offer(tmp_path: Path) -> None:
    engine = engine_at(tmp_path)
    dark = context().model_copy(update={"daylight": False})
    with pytest.raises(TransitionError, match="after dark"):
        engine.offer("three-colors", dark, "calm_naturalist")


def test_xp_streak_bonus_and_skip_reset(tmp_path: Path) -> None:
    engine = engine_at(tmp_path)
    for quest_id in ("three-colors", "sound-layers"):
        engine.offer(quest_id, context(), "calm_naturalist")
        engine.accept()
        engine.request_verification()
        result = engine.verify(
            VerificationEvidence(
                passed=True,
                source="user_confirmation",
                detail="deterministic scripted evidence",
            )
        )
    assert result.progress.xp == 22  # 10 + (10 base + 2 streak bonus)
    assert result.progress.streak == 2

    engine.offer("bark-patterns", context(), "calm_naturalist")
    skipped = engine.skip()
    assert skipped.state is QuestState.SKIPPED
    assert skipped.progress.streak == 0
    assert skipped.progress.xp == 22
