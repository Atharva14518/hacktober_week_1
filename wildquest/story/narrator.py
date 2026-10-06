"""Persona narration; prose is always checked by deterministic safety rules."""

from __future__ import annotations

import re
from enum import Enum
from typing import Callable

from wildquest.quests.models import PlaceContext, Quest
from wildquest.safety.rules import SafetyGuard
from wildquest.story.llm import TextGenerator


class Persona(str, Enum):
    EPIC_FANTASY = "epic_fantasy"
    CALM_NATURALIST = "calm_naturalist"
    LOCAL_GUIDE = "local_guide"


_PERSONA_GUIDANCE: dict[Persona, str] = {
    Persona.EPIC_FANTASY: "Speak like a warm epic-fantasy guide without violence.",
    Persona.CALM_NATURALIST: "Speak like a calm, precise field naturalist.",
    Persona.LOCAL_GUIDE: (
        "Speak as a friendly local guide with light, natural Hinglish and Marathi "
        "flavour; keep it understandable to an English speaker."
    ),
}


class Narrator:
    def __init__(
        self,
        generator: TextGenerator,
        safety: SafetyGuard | None = None,
        latency_sink: Callable[[str, float, float, bool], None] | None = None,
    ) -> None:
        self.generator = generator
        self.safety = safety or SafetyGuard()
        self.latency_sink = latency_sink

    def narrate(self, quest: Quest, context: PlaceContext, persona: Persona) -> str:
        system = (
            "You narrate a quest in 2 to 4 short spoken sentences. "
            + _PERSONA_GUIDANCE[persona]
            + " Never claim the quest is complete. Never direct the hiker off a marked "
            "trail, near edges or water, to touch or eat plants or animals, or onward "
            "after dark."
        )
        user = (
            f"Place: {context.place_name}. Weather: {context.weather_note}. "
            f"Quest seed: {quest.prompt_seed} Safety: {quest.safety_notes}"
        )
        try:
            generation = self.generator.generate(system, user)
            text = _limit_sentences(generation.text, 4)
            if not text:
                raise ValueError("empty narration")
            if _sentence_count(text) < 2:
                text += " Take your time and stay on the marked trail."
            self._log(generation.first_token_s, generation.total_s, True)
        except (RuntimeError, ValueError):
            text = f"{quest.prompt_seed} {quest.hint}"
            self._log(0.0, 0.0, False)
        return self.safety.safe_narration(text, quest)

    def _log(self, first: float, total: float, success: bool) -> None:
        if self.latency_sink is not None:
            self.latency_sink("narrator", first, total, success)


def _limit_sentences(text: str, limit: int) -> str:
    sentences = [part.strip() for part in re.findall(r"[^.!?]+[.!?]?", text) if part.strip()]
    return " ".join(sentences[:limit]).strip()


def _sentence_count(text: str) -> int:
    return len([part for part in re.findall(r"[^.!?]+[.!?]?", text) if part.strip()])
