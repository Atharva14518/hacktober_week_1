#!/usr/bin/env python3
"""One local-Ollama smoke conversation for the Phase 2 quest engine."""

from __future__ import annotations

from pathlib import Path

from wildquest.core.store import QuestStore
from wildquest.quests.conversation import QuestConversation
from wildquest.quests.engine import QuestEngine
from wildquest.quests.models import PlaceContext, load_quests
from wildquest.story.intent import IntentParser
from wildquest.story.llm import OllamaGenerator
from wildquest.story.narrator import Narrator, Persona


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    quests = load_quests(ROOT / "data/quests")
    store = QuestStore(ROOT / "artifacts/phase2-smoke.db")
    engine = QuestEngine(quests, store)
    context = PlaceContext(
        place_name="Sahyadri marked trail",
        daylight=True,
        dry=True,
        on_marked_trail=True,
        weather_note="clear and mild",
    )
    if engine.snapshot().state.value in {"offered", "active", "verifying"}:
        engine.end("reset previous smoke run")
    offered = engine.offer("three-colors", context, Persona.LOCAL_GUIDE.value)
    generator = OllamaGenerator()
    narrator = Narrator(generator, latency_sink=store.log_llm_latency)
    assert offered.quest is not None
    print(narrator.narrate(offered.quest, context, Persona.LOCAL_GUIDE))
    engine.accept()
    conversation = QuestConversation(
        engine, IntentParser(generator, latency_sink=store.log_llm_latency)
    )
    result = conversation.handle("I found all three colors. I am done.")
    print(f"intent={result.intent.value} state={result.snapshot.state.value}")
    print(f"xp={result.snapshot.progress.xp} (must remain zero before verification)")


if __name__ == "__main__":
    main()
