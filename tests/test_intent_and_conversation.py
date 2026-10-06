from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from wildquest.core.store import QuestStore
from wildquest.quests.conversation import QuestConversation
from wildquest.quests.engine import QuestEngine, QuestState, VerificationEvidence
from wildquest.quests.models import PlaceContext, load_quests
from wildquest.story.intent import Intent, IntentParser
from wildquest.story.llm import Generation


QUESTS = load_quests(Path(__file__).parents[1] / "data/quests")


class FakeGenerator:
    def __init__(self, outputs: Iterable[str]) -> None:
        self.outputs = iter(outputs)

    def generate(
        self, system: str, user: str, json_schema: dict[str, Any] | None = None
    ) -> Generation:
        return Generation(next(self.outputs), 0.01, 0.02)


@pytest.mark.parametrize(
    ("speech", "expected"),
    [
        ("I finished it", Intent.DONE),
        ("skip this one", Intent.SKIP),
        ("give me a hint", Intent.HINT),
        ("please say it again", Intent.REPEAT),
        ("I am exhausted", Intent.TIRED),
        ("stop the game", Intent.STOP),
        ("lovely weather", Intent.UNKNOWN),
        ("झालं", Intent.DONE),
    ],
)
def test_invalid_json_uses_keyword_fallback_without_crashing(
    speech: str, expected: Intent
) -> None:
    parser = IntentParser(FakeGenerator(["not json", '{"wrong":"shape"}']))
    assert parser.parse(speech).intent is expected


def test_valid_strict_json_is_accepted() -> None:
    parser = IntentParser(FakeGenerator(['{"intent":"hint"}']))
    assert parser.parse("anything").intent is Intent.HINT


def test_extra_json_fields_are_rejected_and_fall_back() -> None:
    parser = IntentParser(
        FakeGenerator(
            [
                '{"intent":"done","quest_complete":true}',
                '{"intent":"done","quest_complete":true}',
            ]
        )
    )
    assert parser.parse("nothing relevant").intent is Intent.UNKNOWN


def test_llm_done_can_only_request_verification(tmp_path: Path) -> None:
    store = QuestStore(tmp_path / "quest.db")
    engine = QuestEngine(QUESTS, store)
    engine.offer(
        "three-colors",
        PlaceContext(
            place_name="Test Trail", daylight=True, dry=True, on_marked_trail=True
        ),
        "calm_naturalist",
    )
    engine.accept()
    conversation = QuestConversation(
        engine, IntentParser(FakeGenerator(['{"intent":"done"}']))
    )

    result = conversation.handle("I did it")
    assert result.snapshot.state is QuestState.VERIFYING
    assert result.snapshot.progress.xp == 0

    completed = engine.verify(
        VerificationEvidence(
            passed=True,
            source="user_confirmation",
            detail="application verifier accepted evidence",
        )
    )
    assert completed.state is QuestState.COMPLETED


def test_scripted_hint_repeat_skip_conversation(tmp_path: Path) -> None:
    engine = QuestEngine(QUESTS, QuestStore(tmp_path / "quest.db"))
    engine.offer(
        "three-colors",
        PlaceContext(
            place_name="Test Trail", daylight=True, dry=True, on_marked_trail=True
        ),
        "local_guide",
    )
    engine.accept()
    conversation = QuestConversation(
        engine,
        IntentParser(
            FakeGenerator(
                ['{"intent":"hint"}', '{"intent":"repeat"}', '{"intent":"skip"}']
            )
        ),
    )
    assert conversation.handle("help").snapshot.state is QuestState.ACTIVE
    assert conversation.handle("again").snapshot.state is QuestState.ACTIVE
    assert conversation.handle("next").snapshot.state is QuestState.SKIPPED
    assert engine.snapshot().progress.streak == 0


@pytest.mark.parametrize("intent", ["tired", "stop"])
def test_tired_and_stop_end_the_quest(tmp_path: Path, intent: str) -> None:
    engine = QuestEngine(QUESTS, QuestStore(tmp_path / f"{intent}.db"))
    engine.offer(
        "three-colors",
        PlaceContext(
            place_name="Test Trail", daylight=True, dry=True, on_marked_trail=True
        ),
        "local_guide",
    )
    engine.accept()
    conversation = QuestConversation(
        engine, IntentParser(FakeGenerator([f'{{"intent":"{intent}"}}']))
    )
    assert conversation.handle(intent).snapshot.state is QuestState.ENDED
