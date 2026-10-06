from pathlib import Path

from wildquest.quests.models import PlaceContext, load_quests
from wildquest.safety.rules import SafetyGuard


QUESTS = load_quests(Path(__file__).parents[1] / "data/quests")


def safe_context(**changes: bool) -> PlaceContext:
    values = {
        "place_name": "Test Trail",
        "daylight": True,
        "dry": True,
        "on_marked_trail": True,
        "good_visibility": True,
        "low_wind": True,
        "quiet": True,
        "level_ground": True,
        "wide_trail": True,
        "near_edge": False,
        "near_water": False,
    }
    values.update(changes)
    return PlaceContext.model_validate(values)


def test_safety_blocks_darkness_edges_water_and_off_trail() -> None:
    quest = QUESTS["three-colors"]
    guard = SafetyGuard()
    for context in (
        safe_context(daylight=False),
        safe_context(near_edge=True),
        safe_context(near_water=True),
        safe_context(on_marked_trail=False),
    ):
        assert not guard.evaluate(quest, context).allowed


def test_safety_checks_quest_specific_requirements() -> None:
    quest = QUESTS["gentle-incline-rhythm"]
    decision = SafetyGuard().evaluate(quest, safe_context(dry=False))
    assert not decision.allowed
    assert "requires dry" in decision.reasons


def test_safety_code_overrides_unsafe_llm_narration() -> None:
    quest = QUESTS["three-colors"]
    output = SafetyGuard().safe_narration(
        "Leave the trail and walk to the cliff edge.", quest
    )
    assert "Stay on the marked trail" in output
    assert "cliff edge" not in output

