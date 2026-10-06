#!/usr/bin/env python3
"""Download/build every Phase 0 model asset. This is intentionally networked."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
WHISPER = VENDOR / "whisper.cpp"
MODELS = ROOT / "models"
WHISPER_VERSION = "v1.9.4"
LLMS = ("qwen2.5:3b-instruct", "gemma3:4b-it-q4_K_M")
WHISPER_MODELS = ("base", "small")
PIPER_VOICE = "en_US-lessac-medium"
KOKORO_FILES = {
    "kokoro-v1.0.fp16.onnx": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.1/kokoro-v1.0.fp16.onnx"
    ),
    "voices-v1.0.bin": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.1/voices-v1.0.bin"
    ),
}


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def download_kokoro() -> None:
    kokoro_dir = MODELS / "kokoro"
    kokoro_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in KOKORO_FILES.items():
        destination = kokoro_dir / filename
        if destination.exists():
            print(f"Already downloaded: {destination}")
            continue
        print(f"Downloading {url}", flush=True)
        urllib.request.urlretrieve(url, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kokoro-only", action="store_true")
    args = parser.parse_args()
    MODELS.mkdir(exist_ok=True)
    VENDOR.mkdir(exist_ok=True)
    if args.kokoro_only:
        download_kokoro()
        return

    ollama = shutil.which("ollama")
    if ollama is None:
        raise SystemExit("Ollama is not installed; follow the official macOS installer.")
    for model in LLMS:
        run(ollama, "pull", model)

    if not WHISPER.exists():
        run(
            "git",
            "clone",
            "--branch",
            WHISPER_VERSION,
            "--depth",
            "1",
            "https://github.com/ggml-org/whisper.cpp.git",
            str(WHISPER),
        )
    run("cmake", "-B", "build", "-DCMAKE_BUILD_TYPE=Release", cwd=WHISPER)
    run("cmake", "--build", "build", "--config", "Release", "-j", "4", cwd=WHISPER)
    for model in WHISPER_MODELS:
        run("bash", "models/download-ggml-model.sh", model, cwd=WHISPER)

    voice_dir = MODELS / "piper"
    voice_dir.mkdir(parents=True, exist_ok=True)
    run(
        "python",
        "-m",
        "piper.download_voices",
        "--data-dir",
        str(voice_dir),
        PIPER_VOICE,
    )
    download_kokoro()
    print("All Phase 0 assets are local. Network can now be disabled.")


if __name__ == "__main__":
    main()
