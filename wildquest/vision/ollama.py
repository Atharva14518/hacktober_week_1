"""Loopback-only Ollama VLM adapter with strict JSON retry and fail-closed fallback."""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from wildquest.vision.models import VisionAnalysis, VisionAnswer
from wildquest.vision.safety import validate_vision_target


MAX_IMAGE_BYTES = 10 * 1024 * 1024


class VisionClassifier(Protocol):
    def analyze(self, image_path: Path, target: str) -> VisionAnalysis: ...


class OllamaVisionClassifier:
    """Call a predownloaded Ollama model through loopback only."""

    def __init__(self, model: str = "qwen2.5vl:3b", retries: int = 1) -> None:
        if retries not in {0, 1}:
            raise ValueError("vision JSON retries must be zero or one")
        self.model = model
        self.retries = retries

    def analyze(self, image_path: Path, target: str) -> VisionAnalysis:
        safe_target = validate_vision_target(target)
        image = image_path.read_bytes()
        if not image or len(image) > MAX_IMAGE_BYTES:
            raise ValueError("image must be between 1 byte and 10 MiB")

        first_token_s = 0.0
        total_s = 0.0
        error: str | None = None
        for attempt in range(1, self.retries + 2):
            prompt = _prompt(safe_target, retry=attempt > 1)
            try:
                raw, first_token_s, total_s = self._generate(image, prompt)
                answer = VisionAnswer.model_validate_json(raw, strict=True)
                return VisionAnalysis(
                    image_path=str(image_path),
                    target=safe_target,
                    model=self.model,
                    answer=answer,
                    first_token_s=first_token_s,
                    total_s=total_s,
                    parse_valid=True,
                    attempts=attempt,
                )
            except (ValidationError, json.JSONDecodeError, RuntimeError) as exc:
                error = str(exc)[:300]

        return VisionAnalysis(
            image_path=str(image_path),
            target=safe_target,
            model=self.model,
            answer=VisionAnswer(answer="no", confidence=0.0),
            first_token_s=first_token_s,
            total_s=total_s,
            parse_valid=False,
            attempts=self.retries + 1,
            error=error or "invalid model response",
        )

    def _generate(self, image: bytes, prompt: str) -> tuple[str, float, float]:
        inference_image = _inference_copy(image)
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(inference_image).decode("ascii")],
                }
            ],
            "format": VisionAnswer.model_json_schema(),
            "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 40},
        }
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        start = time.perf_counter()
        first: float | None = None
        chunks: list[str] = []
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                for line in response:
                    item = json.loads(line)
                    content = item.get("message", {}).get("content", "")
                    if content and first is None:
                        first = time.perf_counter() - start
                    chunks.append(content)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("local Ollama vision model is unavailable") from exc
        total = time.perf_counter() - start
        return "".join(chunks).strip(), first or total, total


def _inference_copy(image: bytes) -> bytes:
    """Bound visual token count on the 8 GB target while retaining scene detail."""
    try:
        with Image.open(io.BytesIO(image)) as source:
            prepared = ImageOps.exif_transpose(source).convert("RGB")
            prepared.thumbnail((512, 512))
            output = io.BytesIO()
            prepared.save(output, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("image is not safely decodable") from exc
    return output.getvalue()


def _prompt(target: str, *, retry: bool) -> str:
    correction = " Your previous output was invalid; emit JSON only." if retry else ""
    return (
        "Inspect only the attached image. Answer whether it visibly shows the target: "
        f"{target!r}. Do not infer objects outside the frame. Return exactly a JSON "
        'object with keys "answer" ("yes" or "no") and "confidence" (0 to 1). '
        "Confidence is how clearly the pixels support the answer. If uncertain, answer "
        f'"no". Never assess whether a plant or animal is edible.{correction}'
    )
