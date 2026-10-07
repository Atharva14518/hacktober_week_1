"""Local image normalization and webcam capture."""

from __future__ import annotations

import io
import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def normalize_image(data: bytes, directory: Path) -> Path:
    """Decode pixels, discard metadata, resize, and assign a safe local name."""
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("image must be between 1 byte and 10 MiB")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{uuid.uuid4().hex}.jpg"
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600, 1600))
            image.save(destination, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("upload is not a safe, decodable image") from exc
    return destination


def capture_webcam(
    destination: Path, *, device: str = "0", timeout_s: float = 15.0
) -> Path:
    """Capture one frame from macOS AVFoundation using local FFmpeg."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "avfoundation",
        "-framerate",
        "30",
        "-i",
        f"{device}:none",
        "-frames:v",
        "1",
        "-y",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required for webcam capture") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "webcam capture failed; check macOS camera permission or --camera-device"
        ) from exc
    return destination
