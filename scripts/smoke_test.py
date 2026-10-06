#!/usr/bin/env python3
"""Offline microphone -> STT -> local LLM -> TTS Phase 0 smoke test."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path

from piper import PiperVoice


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LLM = "qwen2.5:3b-instruct"
DEFAULT_WHISPER = "base"
DEFAULT_VOICE = "en_US-lessac-medium"


@dataclass(frozen=True)
class Timings:
    record_s: float
    stt_s: float
    llm_first_token_s: float
    llm_total_s: float
    tts_s: float


def log_timings(
    timings: Timings,
    llm_model: str,
    whisper_model: str,
    database: Path = ROOT / "data/wildquest.db",
) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    total_s = timings.record_s + timings.stt_s + timings.llm_total_s + timings.tts_s
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS turn_latency (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                llm_model TEXT NOT NULL,
                whisper_model TEXT NOT NULL,
                record_ms REAL NOT NULL,
                stt_ms REAL NOT NULL,
                llm_first_token_ms REAL NOT NULL,
                llm_total_ms REAL NOT NULL,
                tts_ms REAL NOT NULL,
                turn_total_ms REAL NOT NULL,
                transport TEXT NOT NULL CHECK (transport = 'loopback-only')
            )
            """
        )
        connection.execute(
            """
            INSERT INTO turn_latency (
                llm_model, whisper_model, record_ms, stt_ms,
                llm_first_token_ms, llm_total_ms, tts_ms, turn_total_ms, transport
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'loopback-only')
            """,
            (
                llm_model,
                whisper_model,
                round(timings.record_s * 1000, 3),
                round(timings.stt_s * 1000, 3),
                round(timings.llm_first_token_s * 1000, 3),
                round(timings.llm_total_s * 1000, 3),
                round(timings.tts_s * 1000, 3),
                round(total_s * 1000, 3),
            ),
        )


def extract_transcript(output: str) -> str:
    segments: list[str] = []
    for line in output.splitlines():
        match = re.match(r"^\[[^]]+\]\s+(.*)$", line.strip())
        if match:
            segments.append(match.group(1).strip())
    return " ".join(filter(None, segments)).strip()


def record(path: Path, seconds: int = 5) -> float:
    start = time.perf_counter()
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "avfoundation", "-i", ":0", "-t", str(seconds),
            "-ac", "1", "-ar", "16000", str(path),
        ],
        check=True,
    )
    return time.perf_counter() - start


def transcribe(audio: Path, model_name: str) -> tuple[str, float]:
    binary = ROOT / "vendor/whisper.cpp/build/bin/whisper-cli"
    model = ROOT / f"vendor/whisper.cpp/models/ggml-{model_name}.bin"
    if not binary.exists() or not model.exists():
        raise SystemExit("whisper.cpp assets missing; run `make prefetch` while online.")
    start = time.perf_counter()
    result = subprocess.run(
        [str(binary), "-m", str(model), "-f", str(audio), "-l", "auto"],
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed = time.perf_counter() - start
    return extract_transcript(result.stdout), elapsed


def ollama_chat(prompt: str, model: str) -> tuple[str, float, float]:
    body = json.dumps(
        {
            "model": model,
            "stream": True,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Wild Quest, a concise hiking game master. Reply in at "
                        "most two spoken sentences. Never direct anyone off-trail, toward "
                        "edges or water, to touch/eat wildlife, or to continue after dark."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "options": {"num_ctx": 2048, "temperature": 0.4},
        }
    ).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    first: float | None = None
    chunks: list[str] = []
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw in response:
                data = json.loads(raw)
                content = data.get("message", {}).get("content", "")
                if content and first is None:
                    first = time.perf_counter() - start
                chunks.append(content)
    except urllib.error.URLError as error:
        raise SystemExit(
            "Local Ollama server is unavailable. Start it with `ollama serve`."
        ) from error
    total = time.perf_counter() - start
    return "".join(chunks).strip(), first or total, total


def synthesize(text: str, voice_name: str, output: Path) -> float:
    voice_dir = ROOT / "models/piper"
    model = voice_dir / f"{voice_name}.onnx"
    config = voice_dir / f"{voice_name}.onnx.json"
    if not model.exists() or not config.exists():
        raise SystemExit("Piper voice missing; run `make prefetch` while online.")
    start = time.perf_counter()
    voice = PiperVoice.load(str(model), config_path=str(config))
    with wave.open(str(output), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return time.perf_counter() - start


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, help="Use a local WAV instead of the mic")
    parser.add_argument("--no-play", action="store_true")
    parser.add_argument("--llm", default=os.getenv("WILDQUEST_LLM_MODEL", DEFAULT_LLM))
    parser.add_argument(
        "--whisper", default=os.getenv("WILDQUEST_WHISPER_MODEL", DEFAULT_WHISPER)
    )
    parser.add_argument("--voice", default=os.getenv("WILDQUEST_PIPER_VOICE", DEFAULT_VOICE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    audio = args.audio or artifacts / "microphone.wav"
    print("Wild Quest Phase 0 — runtime is local-only", flush=True)
    if args.audio:
        record_s = 0.0
    else:
        print("Recording for 5 seconds. Speak now…", flush=True)
        record_s = record(audio)
    transcript, stt_s = transcribe(audio, args.whisper)
    if not transcript:
        transcript = "Begin a safe trail quest for me."
        print("No speech detected; using a safe local fallback prompt.", file=sys.stderr)
    print(f"You: {transcript}", flush=True)
    reply, first_s, llm_s = ollama_chat(transcript, args.llm)
    if not reply:
        reply = "Stay on the marked trail and listen for three different natural sounds."
    print(f"Wild Quest: {reply}", flush=True)
    output = artifacts / "reply.wav"
    tts_s = synthesize(reply, args.voice, output)
    if not args.no_play:
        subprocess.run(["afplay", str(output)], check=True)
    timings = Timings(record_s, stt_s, first_s, llm_s, tts_s)
    log_timings(timings, args.llm, args.whisper)
    print("\nStage timings")
    print(f"  record:          {timings.record_s:.3f}s")
    print(f"  STT:             {timings.stt_s:.3f}s")
    print(f"  LLM first token: {timings.llm_first_token_s:.3f}s")
    print(f"  LLM total:       {timings.llm_total_s:.3f}s")
    print(f"  TTS:             {timings.tts_s:.3f}s")
    print(f"  turn total:      {record_s + stt_s + llm_s + tts_s:.3f}s")
    print(f"  SQLite log:      {ROOT / 'data/wildquest.db'}")


if __name__ == "__main__":
    main()
