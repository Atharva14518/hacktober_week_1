#!/usr/bin/env python3
"""Run one safe offline BirdNET quest from prompt through spoken result."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from wildquest.birds import BirdNetLiteRT, BirdQuestService, load_bird_quest_specs
from wildquest.core.store import QuestStore
from wildquest.place import ContextBuilder, LocationPack, UserConditions
from wildquest.quests.engine import QuestEngine, QuestState
from wildquest.quests.models import PlaceContext, load_quests
from wildquest.voice import PiperSpeaker, record_microphone


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quest",
        choices=("hear-common-myna", "discover-new-bird"),
        default="discover-new-bird",
    )
    parser.add_argument("--trail", default="sinhagad")
    parser.add_argument("--audio", type=Path, help="analyze a local clip instead of mic")
    parser.add_argument(
        "--lab",
        action="store_true",
        help="use simulated safe daylight; requires --audio and is never for a hike",
    )
    parser.add_argument("--seconds", type=int, default=12)
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("WILDQUEST_BIRD_CONFIDENCE", "0.25")),
    )
    parser.add_argument("--database", type=Path, default=ROOT / "data/wildquest.db")
    parser.add_argument("--no-play", action="store_true")
    return parser.parse_args()


def safe_context(args: argparse.Namespace) -> PlaceContext:
    if args.lab:
        if args.audio is None:
            raise SystemExit("--lab requires --audio; it cannot enable a live field quest")
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
        raise SystemExit(f"cannot start bird recording from {snapshot.state.value}")
    if snapshot.quest.id != quest_id:
        raise SystemExit(f"active quest is {snapshot.quest.id}, not {quest_id}")


def main() -> int:
    args = parse_args()
    quests = load_quests(ROOT / "data/quests")
    specs = load_bird_quest_specs(ROOT / "data/bird_quests.yaml")
    store = QuestStore(args.database)
    engine = QuestEngine(quests, store)
    activate(engine, args.quest, safe_context(args))

    print("Loading local BirdNET model before recording...", flush=True)
    classifier = BirdNetLiteRT(
        assets=ROOT / "models/birdnet",
        species_list=ROOT / "data/species/maharashtra_birdnet_v2.4.txt",
        threshold=args.threshold,
    )
    speaker = PiperSpeaker(ROOT / "models/piper", "en_US-lessac-medium")
    artifact_dir = ROOT / "artifacts"
    prompt = quests[args.quest].prompt_seed
    prompt_audio = artifact_dir / "bird_prompt.wav"
    speaker.synthesize(prompt, prompt_audio)
    print(f"Wild Quest: {prompt}", flush=True)
    if not args.no_play:
        speaker.play(prompt_audio)

    audio = args.audio or artifact_dir / "bird_recording.wav"
    if args.audio is None:
        print(f"Recording {args.seconds} seconds. Listen without moving...", flush=True)
        record_s = record_microphone(audio, args.seconds)
    else:
        record_s = 0.0

    result_started = time.perf_counter()
    outcome = BirdQuestService(engine, store, classifier, specs).run(audio)
    result_audio = artifact_dir / "bird_result.wav"
    tts_s = speaker.synthesize(outcome.spoken_result, result_audio)
    result_ready_s = time.perf_counter() - result_started
    store.log_bird_turn_latency(
        outcome.analysis_id,
        record_s=record_s,
        birdnet_s=outcome.analysis.inference_s,
        tts_s=tts_s,
        result_ready_s=result_ready_s,
    )
    print(f"Wild Quest: {outcome.spoken_result}", flush=True)
    if not args.no_play:
        speaker.play(result_audio)

    print("\nStage timings")
    print(f"  record:              {record_s:.3f}s")
    print(f"  BirdNET inference:   {outcome.analysis.inference_s:.3f}s")
    print(f"  Piper TTS:           {tts_s:.3f}s")
    print(f"  result ready:        {result_ready_s:.3f}s after recording")
    print(f"  detections logged:   {len(outcome.analysis.detections)}")
    print(f"  quest state:         {outcome.snapshot.state.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
