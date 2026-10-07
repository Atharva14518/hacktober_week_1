"""Photo quest flow with a conservative application-owned verification gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wildquest.core.store import QuestStore
from wildquest.quests.engine import EngineSnapshot, QuestEngine, QuestState, VerificationEvidence
from wildquest.quests.models import QuestType
from wildquest.vision.models import (
    VisionAnalysis,
    VisionQuestSpec,
    VisionVerification,
)
from wildquest.vision.ollama import VisionClassifier
from wildquest.vision.safety import validate_vision_target


@dataclass(frozen=True)
class VisionQuestOutcome:
    analysis_id: int
    analysis: VisionAnalysis
    verification: VisionVerification
    snapshot: EngineSnapshot
    spoken_result: str


class VisionQuestService:
    def __init__(
        self,
        engine: QuestEngine,
        store: QuestStore,
        classifier: VisionClassifier,
        specs: dict[str, VisionQuestSpec],
    ) -> None:
        self.engine = engine
        self.store = store
        self.classifier = classifier
        self.specs = specs

    def run(self, image_path: Path) -> VisionQuestOutcome:
        before, spec = self._active_spec()
        target = validate_vision_target(spec.target)
        analysis = self.classifier.analyze(image_path, target)
        passed = (
            analysis.parse_valid
            and analysis.answer.answer == "yes"
            and analysis.answer.confidence >= spec.confidence_threshold
        )
        if passed:
            reason = (
                f"vision gate accepted yes at {analysis.answer.confidence:.0%} "
                f"(threshold {spec.confidence_threshold:.0%})"
            )
        else:
            reason = (
                f"vision gate did not meet {spec.confidence_threshold:.0%} threshold"
            )
        verification = VisionVerification(passed=passed, reason=reason)
        analysis_id = self.store.log_vision_analysis(
            before, analysis, spec.confidence_threshold, accepted=passed
        )

        self.engine.request_verification()
        snapshot = self.engine.verify(
            VerificationEvidence(passed=passed, source="sensor", detail=reason)
        )
        return VisionQuestOutcome(
            analysis_id=analysis_id,
            analysis=analysis,
            verification=verification,
            snapshot=snapshot,
            spoken_result=_spoken_result(analysis, spec, passed),
        )

    def trust_me(self) -> EngineSnapshot:
        """Explicit human fallback, available only after a failed model attempt."""
        before, spec = self._active_spec()
        validate_vision_target(spec.target)
        if not self.store.has_failed_vision_attempt(before):
            raise RuntimeError("trust-me requires a failed vision attempt for this quest")
        self.engine.request_verification()
        return self.engine.verify(
            VerificationEvidence(
                passed=True,
                source="user_confirmation",
                detail="explicit trust-me fallback after failed photo verification",
            )
        )

    def handle_spoken_fallback(self, speech: str) -> EngineSnapshot:
        """Accept only the explicit voice phrase; no VLM can trigger this path."""
        normalized = " ".join(speech.casefold().split()).strip(".,!?")
        if normalized != "trust me":
            raise RuntimeError("spoken fallback requires the explicit phrase 'trust me'")
        return self.trust_me()

    def _active_spec(self) -> tuple[EngineSnapshot, VisionQuestSpec]:
        snapshot = self.engine.snapshot()
        if snapshot.state is not QuestState.ACTIVE or snapshot.quest is None:
            raise RuntimeError("vision verification requires an active quest")
        if snapshot.quest.type is not QuestType.PHOTO:
            raise RuntimeError("active quest is not a photo quest")
        spec = self.specs.get(snapshot.quest.id)
        if spec is None:
            raise RuntimeError(f"photo quest {snapshot.quest.id!r} has no vision spec")
        return snapshot, spec


def _spoken_result(
    analysis: VisionAnalysis, spec: VisionQuestSpec, passed: bool
) -> str:
    if passed:
        return "Photo accepted. The Python quest gate verified this challenge."
    if not analysis.parse_valid:
        return (
            "I could not validate the vision model response. Try another photo, or say "
            "trust me to continue."
        )
    return (
        f"I could not verify that photo confidently enough. My answer was "
        f"{analysis.answer.answer} at {analysis.answer.confidence:.0%}; the gate needs "
        f"{spec.confidence_threshold:.0%}. Try again, or say trust me to continue."
    )
