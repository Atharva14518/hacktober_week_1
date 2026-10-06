#!/usr/bin/env python3
"""Compare local whisper.cpp models on the same speech sample."""

from __future__ import annotations

from pathlib import Path

from scripts.smoke_test import ROOT, transcribe


def main() -> None:
    audio = ROOT / "vendor/whisper.cpp/samples/jfk.wav"
    if not Path(audio).exists():
        raise SystemExit("Whisper sample missing; run `make prefetch`.")
    for model in ("base", "small"):
        transcript, elapsed = transcribe(audio, model)
        print(f"{model}: {elapsed:.3f}s — {transcript}")


if __name__ == "__main__":
    main()
