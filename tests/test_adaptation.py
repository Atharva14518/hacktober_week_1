from pathlib import Path

import pytest

from wildquest.place import AdaptationAction, AdaptationEngine, OfflineContext
from wildquest.quests.models import load_quests


QUESTS = load_quests(Path(__file__).parents[1] / "data/quests")


def context(**changes: object) -> OfflineContext:
    values: dict[str, object] = {
        "place_name": "Test Trail",
        "local_time": "2026-10-07T12:00+05:30",
        "daylight": True,
        "daylight_remaining_min": 360,
        "rain": False,
        "tired": False,
        "slow": False,
        "on_marked_trail": True,
        "near_edge": False,
        "near_water": False,
        "temperature_c": 25.0,
        "precipitation_probability": 0,
        "wind_speed_kmh": 8.0,
        "elevation_m": 620,
        "nearby_pois": (),
        "trail_notes": (),
        "safety_reminders": ("Stay on the marked trail.",),
        "forecast_stale": False,
    }
    values.update(changes)
    return OfflineContext.model_validate(values)


@pytest.mark.parametrize(
    ("scenario", "quest_id", "changes", "action", "duration"),
    [
        ("normal", "gentle-incline-rhythm", {}, AdaptationAction.KEEP, 5),
        ("rain", "gentle-incline-rhythm", {"rain": True}, AdaptationAction.SWAP, None),
        ("fatigue", "root-step-awareness", {"tired": True}, AdaptationAction.SWAP, None),
        ("easy fatigue", "three-colors", {"tired": True}, AdaptationAction.EASE, 2),
        (
            "low-light move",
            "gentle-incline-rhythm",
            {"daylight_remaining_min": 30},
            AdaptationAction.SWAP,
            None,
        ),
        (
            "low-light stationary",
            "habitat-layers",
            {"daylight_remaining_min": 30},
            AdaptationAction.SHORTEN,
            3,
        ),
        (
            "critical daylight",
            "three-colors",
            {"daylight_remaining_min": 10},
            AdaptationAction.END,
            None,
        ),
        ("slow pace", "level-stride-count", {"slow": True}, AdaptationAction.SHORTEN, 2),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_eight_adaptation_scenarios(
    scenario: str,
    quest_id: str,
    changes: dict[str, object],
    action: AdaptationAction,
    duration: int | None,
) -> None:
    del scenario
    decision = AdaptationEngine(QUESTS).adapt(QUESTS[quest_id], context(**changes))
    assert decision.action is action
    if action is AdaptationAction.END:
        assert decision.selected_quest is None
    else:
        assert decision.selected_quest is not None
        if duration is not None:
            assert decision.selected_quest.duration_min == duration


def test_hazard_context_can_never_return_a_quest() -> None:
    decision = AdaptationEngine(QUESTS).adapt(
        QUESTS["three-colors"], context(near_edge=True)
    )
    assert decision.action is AdaptationAction.END
    assert decision.selected_quest is None
