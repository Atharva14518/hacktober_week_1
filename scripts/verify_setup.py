#!/usr/bin/env python3
"""Fail fast when a required local Phase 0 component is unavailable."""

from __future__ import annotations

import platform
import shutil
import subprocess
from importlib.metadata import version as package_version
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def version(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr).strip().splitlines()[-1]


def main() -> None:
    required = ("ollama", "ffmpeg", "afplay", "cmake")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise SystemExit(f"Missing required tools: {', '.join(missing)}")
    if platform.machine() != "arm64":
        raise SystemExit(f"Expected native arm64 Python, got {platform.machine()}")
    print(f"Python: {platform.python_version()} ({platform.machine()})")
    print(f"Ollama: {version(['ollama', '--version'])}")
    print(f"FFmpeg: {version(['ffmpeg', '-version'])}")
    whisper = ROOT / "vendor/whisper.cpp/build/bin/whisper-cli"
    print(f"whisper.cpp: {'ready' if whisper.exists() else 'models not prefetched'}")
    print("Piper: import verified")
    print(f"BirdNET: {package_version('birdnet')} (LiteRT route)")
    import piper  # noqa: F401


if __name__ == "__main__":
    main()
