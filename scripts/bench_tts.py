#!/usr/bin/env python3
"""Compare the two fully local Phase 0 TTS engines."""

from __future__ import annotations

import time
import wave
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro
from piper import PiperVoice


ROOT = Path(__file__).resolve().parents[1]
TEXT = "Stay on the marked trail and listen for three different natural sounds."


def main() -> None:
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)

    piper_dir = ROOT / "models/piper"
    start = time.perf_counter()
    piper = PiperVoice.load(
        str(piper_dir / "en_US-lessac-medium.onnx"),
        config_path=str(piper_dir / "en_US-lessac-medium.onnx.json"),
    )
    with wave.open(str(artifacts / "piper.wav"), "wb") as output:
        piper.synthesize_wav(TEXT, output)
    piper_s = time.perf_counter() - start

    kokoro_dir = ROOT / "models/kokoro"
    start = time.perf_counter()
    kokoro = Kokoro(
        str(kokoro_dir / "kokoro-v1.0.fp16.onnx"),
        str(kokoro_dir / "voices-v1.0.bin"),
    )
    audio, sample_rate = kokoro.create(TEXT, voice="af_heart", speed=1.0, lang="en-us")
    sf.write(artifacts / "kokoro.wav", audio, sample_rate, subtype="PCM_16")
    kokoro_s = time.perf_counter() - start

    print(f"Piper total: {piper_s:.3f}s")
    print(f"Kokoro total: {kokoro_s:.3f}s")


if __name__ == "__main__":
    main()
