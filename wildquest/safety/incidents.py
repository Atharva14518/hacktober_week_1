"""Deterministic reminders and lost/hurt emergency guidance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SafetyIncident(str, Enum):
    LOST = "lost"
    HURT = "hurt"


@dataclass(frozen=True)
class IncidentResponse:
    incident: SafetyIncident
    spoken_instruction: str


class SafetyAdvisor:
    def reminders(
        self,
        *,
        rain: bool,
        tired: bool,
        slow: bool,
        daylight_remaining_min: int,
        daylight: bool,
    ) -> tuple[str, ...]:
        reminders: list[str] = ["Stay on the marked trail."]
        if rain:
            reminders.append("Wet ground may be slippery; avoid movement quests.")
        if tired:
            reminders.append("Choose a safe rest point and stop if fatigue worsens.")
        elif slow:
            reminders.append("Use a comfortable pace without rushing.")
        if not daylight or daylight_remaining_min <= 10:
            reminders.append("Do not continue after dark; end the quest now.")
        elif daylight_remaining_min <= 45:
            reminders.append("Daylight is low; keep the quest short and prepare to finish.")
        return tuple(reminders)


class IncidentHandler:
    _LOST = ("lost", "can't find the trail", "cannot find the trail", "रस्ता चुक", "हरव")
    _HURT = ("hurt", "injured", "fell", "bleeding", "दुखापत", "जखमी")

    def handle(self, speech: str) -> IncidentResponse | None:
        normalized = " ".join(speech.casefold().split())
        incident: SafetyIncident | None = None
        if any(phrase in normalized for phrase in self._HURT):
            incident = SafetyIncident.HURT
        elif any(phrase in normalized for phrase in self._LOST):
            incident = SafetyIncident.LOST
        if incident is None:
            return None
        situation = "hurt" if incident is SafetyIncident.HURT else "lost"
        return IncidentResponse(
            incident=incident,
            spoken_instruction=(
                f"You may be {situation}. Stop moving and stay put in a safe place "
                "away from edges and water. Wild Quest is not an emergency system. "
                "Use your phone's emergency call now, or ask a nearby person to call "
                "emergency services for you."
            ),
        )
