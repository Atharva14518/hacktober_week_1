from __future__ import annotations

import io
import asyncio
import sqlite3
from pathlib import Path

import pytest
from PIL import Image
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from starlette.datastructures import Headers

from wildquest.core.store import QuestStore
from wildquest.quests.engine import QuestEngine, QuestState
from wildquest.quests.models import PlaceContext, load_quests
from wildquest.vision.images import normalize_image
from wildquest.vision.models import (
    VisionAnalysis,
    VisionAnswer,
    VisionQuestSpec,
    load_vision_quest_specs,
)
from wildquest.vision.ollama import OllamaVisionClassifier
from wildquest.vision.safety import UnsafeVisionTarget, validate_vision_target
from wildquest.vision.service import VisionQuestService
from wildquest.vision.upload import create_upload_app


ROOT = Path(__file__).parents[1]


class FakeClassifier:
    def __init__(self, answer: str, confidence: float, *, valid: bool = True) -> None:
        self.answer = answer
        self.confidence = confidence
        self.valid = valid

    def analyze(self, image_path: Path, target: str) -> VisionAnalysis:
        return VisionAnalysis(
            image_path=str(image_path),
            target=target,
            model="fake-vlm",
            answer=VisionAnswer(answer=self.answer, confidence=self.confidence),
            first_token_s=0.1,
            total_s=0.2,
            parse_valid=self.valid,
            attempts=1,
            error=None if self.valid else "invalid output",
        )


def active_service(
    tmp_path: Path, classifier: FakeClassifier
) -> tuple[VisionQuestService, QuestStore]:
    quests = load_quests(ROOT / "data/quests")
    store = QuestStore(tmp_path / "vision.db")
    engine = QuestEngine(quests, store)
    engine.offer(
        "photo-bird-from-trail",
        PlaceContext(
            place_name="test trail",
            daylight=True,
            dry=True,
            on_marked_trail=True,
        ),
        "calm_naturalist",
    )
    engine.accept()
    specs = load_vision_quest_specs(ROOT / "data/vision_quests.yaml")
    return VisionQuestService(engine, store, classifier, specs), store


def test_answer_is_strict_json_shape() -> None:
    assert VisionAnswer.model_validate_json(
        '{"answer":"yes","confidence":0.9}', strict=True
    ).answer == "yes"
    with pytest.raises(ValidationError):
        VisionAnswer.model_validate_json(
            '{"answer":"yes","confidence":0.9,"reason":"extra"}', strict=True
        )
    with pytest.raises(ValidationError):
        VisionAnswer.model_validate_json(
            '{"answer":true,"confidence":"0.9"}', strict=True
        )


def test_ollama_parser_retries_then_accepts_strict_json(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"small fixture")
    classifier = OllamaVisionClassifier("fixture-model")
    replies = iter(
        [
            ("not json", 0.1, 0.2),
            ('{"answer":"yes","confidence":0.91}', 0.2, 0.3),
        ]
    )
    classifier._generate = lambda image, prompt: next(replies)  # type: ignore[method-assign]
    result = classifier.analyze(path, "a bird")
    assert result.parse_valid is True
    assert result.attempts == 2
    assert result.answer.answer == "yes"


def test_invalid_json_fails_closed_without_crash(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"small fixture")
    classifier = OllamaVisionClassifier("fixture-model")
    classifier._generate = lambda image, prompt: ("{}", 0.1, 0.2)  # type: ignore[method-assign]
    result = classifier.analyze(path, "a bird")
    assert result.parse_valid is False
    assert result.answer == VisionAnswer(answer="no", confidence=0.0)
    assert result.attempts == 2


@pytest.mark.parametrize(
    "target",
    ["is this berry edible", "a plant safe to eat", "medicinal mushroom", "food"],
)
def test_edibility_requests_are_blocked_in_code(target: str) -> None:
    with pytest.raises(UnsafeVisionTarget):
        validate_vision_target(target)


def test_conservative_gate_rejects_below_threshold_then_trust_me_completes(
    tmp_path: Path,
) -> None:
    service, store = active_service(tmp_path, FakeClassifier("yes", 0.79))
    outcome = service.run(tmp_path / "bird.jpg")
    assert outcome.snapshot.state is QuestState.ACTIVE
    assert outcome.verification.passed is False
    assert service.handle_spoken_fallback("Trust me!").state is QuestState.COMPLETED
    with sqlite3.connect(store.path) as connection:
        row = connection.execute(
            "SELECT answer, confidence, threshold, accepted FROM vision_analyses"
        ).fetchone()
    assert row == ("yes", 0.79, 0.8, 0)


def test_high_confidence_model_evidence_completes_only_through_engine(
    tmp_path: Path,
) -> None:
    service, _ = active_service(tmp_path, FakeClassifier("yes", 0.95))
    assert service.engine.snapshot().state is QuestState.ACTIVE
    outcome = service.run(tmp_path / "bird.jpg")
    assert outcome.verification.passed is True
    assert outcome.snapshot.state is QuestState.COMPLETED


def test_trust_me_requires_prior_failed_attempt(tmp_path: Path) -> None:
    service, _ = active_service(tmp_path, FakeClassifier("no", 0.9))
    with pytest.raises(RuntimeError, match="failed vision attempt"):
        service.trust_me()


def test_spoken_fallback_requires_exact_phrase(tmp_path: Path) -> None:
    service, _ = active_service(tmp_path, FakeClassifier("no", 0.9))
    service.run(tmp_path / "bird.jpg")
    with pytest.raises(RuntimeError, match="explicit phrase"):
        service.handle_spoken_fallback("the model should trust itself")


def test_image_normalization_decodes_content_and_strips_input_name(tmp_path: Path) -> None:
    source = io.BytesIO()
    Image.new("RGB", (32, 24), color="green").save(source, format="PNG")
    result = normalize_image(source.getvalue(), tmp_path)
    assert result.suffix == ".jpg"
    assert result.name != "upload.png"
    with Image.open(result) as image:
        assert image.format == "JPEG"
        assert image.size == (32, 24)
    with pytest.raises(ValueError, match="decodable image"):
        normalize_image(b"not actually a jpeg", tmp_path)


def test_local_upload_app_disables_documentation_and_requires_long_token(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="16"):
        create_upload_app(tmp_path, "short")
    app = create_upload_app(tmp_path, "a-secure-session-token")
    paths = {route.path for route in app.routes}
    assert paths == {"/", "/upload"}
    index = next(route.endpoint for route in app.routes if route.path == "/")
    with pytest.raises(HTTPException) as error:
        asyncio.run(index(token_value="wrong-token-value"))
    assert error.value.status_code == 403
    assert "Wild Quest photo" in asyncio.run(
        index(token_value="a-secure-session-token")
    )


def test_upload_endpoint_decodes_and_rewrites_image(tmp_path: Path) -> None:
    app = create_upload_app(tmp_path, "a-secure-session-token")
    upload_endpoint = next(
        route.endpoint for route in app.routes if route.path == "/upload"
    )
    source = io.BytesIO()
    Image.new("RGB", (20, 20), color="blue").save(source, format="PNG")
    upload = UploadFile(
        filename="../../unsafe.png",
        file=io.BytesIO(source.getvalue()),
        headers=Headers({"content-type": "image/png"}),
    )
    result = asyncio.run(
        upload_endpoint(photo=upload, token_value="a-secure-session-token")
    )
    assert result["status"] == "ready"
    assert "unsafe" not in result["image_id"]
    assert (tmp_path / result["image_id"]).is_file()


def test_vision_spec_threshold_is_conservative() -> None:
    with pytest.raises(ValidationError):
        VisionQuestSpec(
            quest_id="photo-bird-from-trail",
            target="a bird",
            confidence_threshold=0.49,
        )
