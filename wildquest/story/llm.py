"""Minimal loopback-only Ollama streaming client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Generation:
    text: str
    first_token_s: float
    total_s: float


class TextGenerator(Protocol):
    def generate(
        self, system: str, user: str, json_schema: dict[str, Any] | None = None
    ) -> Generation: ...


class OllamaGenerator:
    """Calls only the local Ollama daemon; no remote URL is configurable."""

    def __init__(self, model: str = "qwen2.5:3b-instruct") -> None:
        self.model = model

    def generate(
        self, system: str, user: str, json_schema: dict[str, Any] | None = None
    ) -> Generation:
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.1 if json_schema else 0.5, "num_ctx": 2048},
        }
        if json_schema is not None:
            payload["format"] = json_schema
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        start = time.perf_counter()
        first_token_s: float | None = None
        chunks: list[str] = []
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                for line in response:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content and first_token_s is None:
                        first_token_s = time.perf_counter() - start
                    chunks.append(content)
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("local Ollama daemon is unavailable") from error
        total_s = time.perf_counter() - start
        return Generation("".join(chunks).strip(), first_token_s or total_s, total_s)

