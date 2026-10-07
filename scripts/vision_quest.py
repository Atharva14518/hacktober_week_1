#!/usr/bin/env python3
"""Run one offline vision quest from local image capture through spoken result."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from wildquest.core.store import QuestStore
from wildquest.place import ContextBuilder, LocationPack, UserConditions
from wildquest.quests.engine import QuestEngine, QuestState
from wildquest.quests.models import PlaceContext, load_quests
from wildquest.vision.images import capture_webcam
from wildquest.vision.models import load_vision_quest_specs
from wildquest.vision.ollama import OllamaVisionClassifier
from wildquest.vision.service import VisionQuestService
from wildquest.voice import PiperSpeaker


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quest",
        choices=("photo-bird-from-trail", "photo-trail-marker"),
        default="photo-bird-from-trail",
    )
    parser.add_argument("--trail", default="sinhagad")
    parser.add_argument("--image", type=Path, help="local or phone-uploaded image")
    parser.add_argument("--camera-device", default="0")
    parser.add_argument("--model", default=os.getenv("WILDQUEST_VISION_MODEL", "qwen2.5vl:3b"))
    parser.add_argument("--database", type=Path, default=ROOT / "data/wildquest.db")
    parser.add_argument("--trust-me", action="store_true")
    parser.add_argument("--no-play", action="store_true")
    parser.add_argument(
        "--lab",
        action="store_true",
        help="simulate safe daylight; requires --image and is never for a hike",
    )
    return parser.parse_args()


def context_for(args: argparse.Namespace) -> PlaceContext:
    if args.lab:
        if args.image is None:
            raise SystemExit("--lab requires --image")
        return PlaceContext(
            place_name="offline lab fixture",
            daylight=True,
            dry=True,
            on_marked_trail=True,
        )
    pack = LocationPack(ROOT / "data/location_packs" / args.trail)
    now = datetime.now(ZoneInfo(pack.manifest.timezone))
    return ContextBuilder().build(pack, now, UserConditions()).quest_context()


def activate(engine: QuestEngine, quest_id: str, context: PlaceContext) -> None:
    snapshot = engine.snapshot()
    if snapshot.state in {
        QuestState.IDLE,
        QuestState.COMPLETED,
        QuestState.SKIPPED,
        QuestState.ENDED,
    }:
        engine.offer(quest_id, context, "calm_naturalist")
        snapshot = engine.accept()
    elif snapshot.state is QuestState.OFFERED and snapshot.quest is not None:
        if snapshot.quest.id != quest_id:
            raise SystemExit("another quest is already offered")
        snapshot = engine.accept()
    if snapshot.state is not QuestState.ACTIVE or snapshot.quest is None:
        raise SystemExit(f"cannot start photo verification from {snapshot.state.value}")
    if snapshot.quest.id != quest_id:
        raise SystemExit(f"active quest is {snapshot.quest.id}, not {quest_id}")


def main() -> int:
    args = parse_args()
    quests = load_quests(ROOT / "data/quests")
    specs = load_vision_quest_specs(ROOT / "data/vision_quests.yaml")
    store = QuestStore(args.database)
    engine = QuestEngine(quests, store)
    activate(engine, args.quest, context_for(args))
    image = args.image or ROOT / "artifacts" / "vision_webcam.jpg"
    if args.image is None:
        print("Stand still on safe level trail. Capturing one webcam frame...", flush=True)
        capture_webcam(image, device=args.camera_device)
    service = VisionQuestService(
        engine, store, OllamaVisionClassifier(args.model), specs
    )
    started = time.perf_counter()
    outcome = service.run(image)
    snapshot = outcome.snapshot
    spoken = outcome.spoken_result
    if args.trust_me and not outcome.verification.passed:
        snapshot = service.trust_me()
        spoken = "Thanks. I will trust your observation. Quest verified by your confirmation."
    speaker = PiperSpeaker(ROOT / "models/piper", "en_US-lessac-medium")
    output = ROOT / "artifacts" / "vision_result.wav"
    tts_s = speaker.synthesize(spoken, output)
    result_s = time.perf_counter() - started
    print(f"Wild Quest: {spoken}")
    if not args.no_play:
        speaker.play(output)
    print("\nStage timings")
    print(f"  VLM first token: {outcome.analysis.first_token_s:.3f}s")
    print(f"  VLM total:       {outcome.analysis.total_s:.3f}s")
    print(f"  Piper TTS:       {tts_s:.3f}s")
    print(f"  result ready:    {result_s:.3f}s")
    print(f"  quest state:     {snapshot.state.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
