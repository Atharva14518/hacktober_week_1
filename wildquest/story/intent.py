"""Strict intent parsing with bounded retry and deterministic keyword fallback."""

from __future__ import annotations

from enum import Enum
from typing import Callable

from pydantic import BaseModel, ConfigDict, ValidationError

from wildquest.story.llm import TextGenerator


class Intent(str, Enum):
    DONE = "done"
    SKIP = "skip"
    HINT = "hint"
    REPEAT = "repeat"
    TIRED = "tired"
    STOP = "stop"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    intent: Intent


_KEYWORDS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (Intent.STOP, ("stop", "end quest", "quit", "thamb", "थांब")),
    (Intent.TIRED, ("tired", "exhausted", "rest", "thak", "दमलो", "दमले")),
    (Intent.SKIP, ("skip", "another quest", "pass", "nako", "नको")),
    (Intent.HINT, ("hint", "help me", "clue", "madat", "मदत")),
    (
        Intent.REPEAT,
        ("repeat", "say again", "say it again", "what was", "punha", "पुन्हा"),
    ),
    (Intent.DONE, ("done", "finished", "complete", "zala", "झालं", "झाले")),
)

_SYSTEM = """You classify one spoken command for an offline hiking game.
Return exactly one JSON object matching the supplied schema. Do not add prose.
Choose one intent: done, skip, hint, repeat, tired, stop, or unknown.
Never decide whether a quest succeeded: 'done' only means the user claims they are done."""


class IntentParser:
    def __init__(
        self,
        generator: TextGenerator,
        retries: int = 1,
        latency_sink: Callable[[str, float, float, bool], None] | None = None,
    ) -> None:
        self.generator = generator
        self.retries = retries
        self.latency_sink = latency_sink

    def parse(self, speech: str) -> IntentResult:
        for attempt in range(self.retries + 1):
            prompt = f"Speech: {speech!r}"
            if attempt:
                prompt += "\nYour previous output was invalid. Return schema-valid JSON only."
            try:
                generation = self.generator.generate(
                    _SYSTEM, prompt, IntentResult.model_json_schema()
                )
            except RuntimeError:
                self._log(0.0, 0.0, False)
                continue
            try:
                result = IntentResult.model_validate_json(generation.text, strict=True)
            except (ValidationError, ValueError):
                self._log(generation.first_token_s, generation.total_s, False)
                continue
            self._log(generation.first_token_s, generation.total_s, True)
            return result
        return IntentResult(intent=keyword_fallback(speech))

    def _log(self, first: float, total: float, success: bool) -> None:
        if self.latency_sink is not None:
            self.latency_sink("intent", first, total, success)


def keyword_fallback(speech: str) -> Intent:
    normalized = " ".join(speech.casefold().split())
    for intent, keywords in _KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return intent
    return Intent.UNKNOWN
