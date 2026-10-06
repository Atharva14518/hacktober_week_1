"""Bird quest flow: classify, persist evidence, and ask the state machine to verify."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wildquest.birds.birdnet import BirdClassifier
from wildquest.birds.models import (
    BirdAnalysis,
    BirdGoal,
    BirdQuestSpec,
    BirdVerification,
)
from wildquest.core.store import QuestStore
from wildquest.quests.engine import EngineSnapshot, QuestEngine, QuestState, VerificationEvidence
from wildquest.quests.models import QuestType


@dataclass(frozen=True)
class BirdQuestOutcome:
    analysis_id: int
    analysis: BirdAnalysis
    verification: BirdVerification
    snapshot: EngineSnapshot
    spoken_result: str


class BirdQuestService:
    def __init__(
        self,
        engine: QuestEngine,
        store: QuestStore,
        classifier: BirdClassifier,
        specs: dict[str, BirdQuestSpec],
    ) -> None:
        self.engine = engine
        self.store = store
        self.classifier = classifier
        self.specs = specs

    def run(self, audio_path: Path) -> BirdQuestOutcome:
        before = self.engine.snapshot()
        if before.state is not QuestState.ACTIVE or before.quest is None:
            raise RuntimeError("bird verification requires an active quest")
        if before.quest.type is not QuestType.BIRD:
            raise RuntimeError("active quest is not a bird quest")
        spec = self.specs.get(before.quest.id)
        if spec is None:
            raise RuntimeError(f"bird quest {before.quest.id!r} has no detector spec")

        seen_before = self.store.seen_bird_labels()
        analysis = self.classifier.analyze(audio_path)
        analysis_id = self.store.log_bird_analysis(before, analysis)
        verification = verify_bird_goal(spec, analysis, seen_before)

        self.engine.request_verification()
        snapshot = self.engine.verify(
            VerificationEvidence(
                passed=verification.passed,
                source="sensor",
                detail=verification.reason,
            )
        )
        return BirdQuestOutcome(
            analysis_id=analysis_id,
            analysis=analysis,
            verification=verification,
            snapshot=snapshot,
            spoken_result=_spoken_result(verification, analysis),
        )


def verify_bird_goal(
    spec: BirdQuestSpec,
    analysis: BirdAnalysis,
    seen_before: set[str],
) -> BirdVerification:
    if spec.goal is BirdGoal.TARGET:
        match = next(
            (
                detection
                for detection in analysis.detections
                if detection.label == spec.target_label
            ),
            None,
        )
        if match is None:
            return BirdVerification(
                passed=False,
                reason="target species was not detected above the configured threshold",
            )
        return BirdVerification(
            passed=True,
            reason=f"BirdNET detected target {match.common_name}",
            matched=match,
        )

    match = next(
        (
            detection
            for detection in analysis.detections
            if detection.label not in seen_before
        ),
        None,
    )
    if match is None:
        return BirdVerification(
            passed=False,
            reason="no previously unseen species was detected above the threshold",
        )
    return BirdVerification(
        passed=True,
        reason=f"BirdNET detected a new species: {match.common_name}",
        matched=match,
    )


def _spoken_result(
    verification: BirdVerification, analysis: BirdAnalysis
) -> str:
    if verification.passed and verification.matched is not None:
        match = verification.matched
        return (
            f"I detected {match.common_name} at {match.confidence:.0%} confidence. "
            "Quest verified, but treat this as a likely identification, not certainty."
        )
    if analysis.detections:
        top = analysis.detections[0]
        return (
            f"I heard a possible {top.common_name} at {top.confidence:.0%} confidence, "
            "but it does not verify this quest. Stay put and try listening again."
        )
    return (
        "I could not identify a listed bird confidently. That is normal in wind or "
        "overlapping calls; stay on the trail and try again without approaching wildlife."
    )
