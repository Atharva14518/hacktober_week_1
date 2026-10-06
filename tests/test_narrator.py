from pathlib import Path
from typing import Any

from wildquest.quests.models import PlaceContext, load_quests
from wildquest.story.llm import Generation
from wildquest.story.narrator import Narrator, Persona


QUEST = load_quests(Path(__file__).parents[1] / "data/quests")["three-colors"]
CONTEXT = PlaceContext(
    place_name="Sahyadri Trail", daylight=True, dry=True, on_marked_trail=True
)


class FakeGenerator:
    def __init__(self, output: str) -> None:
        self.output = output

    def generate(
        self, system: str, user: str, json_schema: dict[str, Any] | None = None
    ) -> Generation:
        return Generation(self.output, 0.01, 0.02)


def test_all_personas_produce_bounded_spoken_narration() -> None:
    for persona in Persona:
        text = Narrator(
            FakeGenerator("One. Two. Three. Four. This fifth sentence is removed.")
        ).narrate(QUEST, CONTEXT, persona)
        assert "fifth" not in text


def test_unsafe_narration_is_overridden_in_code() -> None:
    narrator = Narrator(FakeGenerator("Leave the trail and wade into the water."))
    text = narrator.narrate(QUEST, CONTEXT, Persona.EPIC_FANTASY)
    assert text.startswith("Stay on the marked trail in daylight.")
    assert "wade" not in text


def test_single_sentence_gets_safe_second_spoken_sentence() -> None:
    narrator = Narrator(FakeGenerator("Find three colors from where you stand."))
    text = narrator.narrate(QUEST, CONTEXT, Persona.CALM_NATURALIST)
    assert text == (
        "Find three colors from where you stand. "
        "Take your time and stay on the marked trail."
    )
