import json
from pathlib import Path

import pytest

from wildquest.birds import (
    BirdAnalysis,
    BirdDetection,
    BirdGoal,
    BirdNetAssets,
    BirdNetLiteRT,
    BirdQuestService,
    BirdQuestSpec,
    load_bird_quest_specs,
)
from wildquest.core.store import QuestStore
from wildquest.quests.engine import QuestEngine, QuestState
from wildquest.quests.models import PlaceContext, load_quests


ROOT = Path(__file__).parents[1]
QUESTS = load_quests(ROOT / "data/quests")
SPECS = load_bird_quest_specs(ROOT / "data/bird_quests.yaml")
MYNA = "Acridotheres tristis_Common Myna"
KOEL = "Eudynamys scolopaceus_Asian Koel"


class FakeClassifier:
    def __init__(self, detections: tuple[BirdDetection, ...]) -> None:
        self.detections = detections

    def analyze(self, audio_path: Path) -> BirdAnalysis:
        return BirdAnalysis(
            audio_path=str(audio_path),
            audio_duration_s=12.0,
            inference_s=0.2,
            threshold=0.25,
            detections=self.detections,
        )


def detection(label: str, confidence: float = 0.9) -> BirdDetection:
    scientific, common = label.split("_", 1)
    return BirdDetection(
        label=label,
        scientific_name=scientific,
        common_name=common,
        confidence=confidence,
        start_s=0.0,
        end_s=3.0,
    )


def active_engine(tmp_path: Path, quest_id: str) -> tuple[QuestEngine, QuestStore]:
    store = QuestStore(tmp_path / "bird.db")
    engine = QuestEngine(QUESTS, store)
    engine.offer(
        quest_id,
        PlaceContext(
            place_name="Test Trail",
            daylight=True,
            dry=True,
            on_marked_trail=True,
        ),
        "calm_naturalist",
    )
    engine.accept()
    return engine, store


def test_target_detection_is_logged_and_completes_state_machine(tmp_path: Path) -> None:
    engine, store = active_engine(tmp_path, "hear-common-myna")
    outcome = BirdQuestService(
        engine, store, FakeClassifier((detection(MYNA, 0.91),)), SPECS
    ).run(tmp_path / "call.wav")

    assert outcome.snapshot.state is QuestState.COMPLETED
    assert outcome.snapshot.progress.xp == 20
    assert outcome.verification.matched is not None
    rows = store.bird_detections()
    assert len(rows) == 1
    assert rows[0].label == MYNA
    assert rows[0].confidence == pytest.approx(0.91)


def test_wrong_species_cannot_complete_target_quest(tmp_path: Path) -> None:
    engine, store = active_engine(tmp_path, "hear-common-myna")
    outcome = BirdQuestService(
        engine, store, FakeClassifier((detection(KOEL),)), SPECS
    ).run(tmp_path / "call.wav")

    assert outcome.snapshot.state is QuestState.ACTIVE
    assert outcome.snapshot.progress.xp == 0
    assert not outcome.verification.passed


def test_any_new_species_uses_prior_sqlite_detection_history(tmp_path: Path) -> None:
    engine, store = active_engine(tmp_path, "discover-new-bird")
    first = BirdQuestService(
        engine, store, FakeClassifier((detection(KOEL),)), SPECS
    ).run(tmp_path / "first.wav")
    assert first.snapshot.state is QuestState.COMPLETED

    engine.offer(
        "discover-new-bird",
        PlaceContext(
            place_name="Test Trail",
            daylight=True,
            dry=True,
            on_marked_trail=True,
        ),
        "calm_naturalist",
    )
    engine.accept()
    repeated = BirdQuestService(
        engine, store, FakeClassifier((detection(KOEL),)), SPECS
    ).run(tmp_path / "again.wav")
    assert repeated.snapshot.state is QuestState.ACTIVE
    assert not repeated.verification.passed


def test_bird_quest_specs_are_strict() -> None:
    assert SPECS["hear-common-myna"].goal is BirdGoal.TARGET
    with pytest.raises(ValueError):
        BirdQuestSpec.model_validate(
            {"quest_id": "bad", "goal": "target", "extra": True}
        )


def test_missing_assets_fail_before_birdnet_can_download(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="prefetch_models.py --birdnet-only"):
        BirdNetLiteRT(
            assets=tmp_path,
            species_list=ROOT / "data/species/maharashtra_birdnet_v2.4.txt",
        )


ASSETS = BirdNetAssets(ROOT / "models/birdnet")


@pytest.mark.skipif(not ASSETS.ready(), reason="BirdNET model has not been prefetched")
def test_public_clip_set_has_documented_pinned_model_accuracy() -> None:
    manifest = json.loads(
        (ROOT / "tests/fixtures/birds/manifest.json").read_text(encoding="utf-8")
    )
    classifier = BirdNetLiteRT(
        assets=ASSETS.root,
        species_list=ROOT / "data/species/maharashtra_birdnet_v2.4.txt",
        threshold=0.25,
    )
    correct = 0
    for clip in manifest["clips"]:
        analysis = classifier.analyze(ROOT / "tests/fixtures/birds" / clip["filename"])
        if any(
            detection.label == clip["expected_label"]
            for detection in analysis.detections
        ):
            correct += 1
    assert correct == 3
