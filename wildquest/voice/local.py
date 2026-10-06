"""Reusable local microphone recording and Piper speech output."""

from __future__ import annotations

import shutil
import subprocess
import time
import wave
from pathlib import Path

from piper import PiperVoice


def record_microphone(path: Path, seconds: int = 12, sample_rate: int = 48_000) -> float:
    if not 10 <= seconds <= 15:
        raise ValueError("bird quest recording must be between 10 and 15 seconds")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for microphone recording")
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "avfoundation",
            "-i",
            ":0",
            "-t",
            str(seconds),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(path),
        ],
        check=True,
    )
    return time.perf_counter() - started


class PiperSpeaker:
    def __init__(self, voice_directory: Path, voice_name: str) -> None:
        model = voice_directory / f"{voice_name}.onnx"
        config = voice_directory / f"{voice_name}.onnx.json"
        if not model.is_file() or not config.is_file():
            raise RuntimeError("Piper voice missing; run `make prefetch` online")
        self.voice = PiperVoice.load(str(model), config_path=str(config))

    def synthesize(self, text: str, output: Path) -> float:
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        with wave.open(str(output), "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file)
        return time.perf_counter() - started

    @staticmethod
    def play(path: Path) -> None:
        subprocess.run(["afplay", str(path)], check=True)
