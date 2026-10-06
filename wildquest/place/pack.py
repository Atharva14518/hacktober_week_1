"""Strict, filesystem-only location pack loader."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: int = Field(ge=1, le=1)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    bbox: tuple[float, float, float, float]
    timezone: str = Field(min_length=1, max_length=80)
    fetched_at: str
    attribution: tuple[str, ...]


class LocationPack:
    """Loaded only from local files; this module has no networking imports."""

    REQUIRED_FILES = (
        "manifest.json",
        "route.gpx",
        "pois.json",
        "elevation.json",
        "sunrise_sunset.json",
        "forecast.json",
        "notes.md",
    )

    def __init__(self, directory: Path) -> None:
        missing = [name for name in self.REQUIRED_FILES if not (directory / name).is_file()]
        if missing:
            raise ValueError(f"incomplete location pack; missing: {', '.join(missing)}")
        self.directory = directory
        self.manifest = PackManifest.model_validate_json(
            (directory / "manifest.json").read_text(encoding="utf-8"), strict=True
        )
        self.pois = self._json("pois.json")
        self.elevation = self._json("elevation.json")
        self.sun = self._json("sunrise_sunset.json")
        self.forecast = self._json("forecast.json")
        self.notes = self._notes(directory / "notes.md")

    def _json(self, name: str) -> dict[str, object]:
        value = json.loads((self.directory / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{name} must contain a JSON object")
        return value

    @staticmethod
    def _notes(path: Path) -> tuple[str, ...]:
        notes = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                notes.append(stripped[2:])
        return tuple(notes[:8])
