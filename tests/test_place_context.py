import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from wildquest.place import ContextBuilder, LocationPack, UserConditions


def make_pack(root: Path) -> LocationPack:
    pack = root / "test-trail"
    pack.mkdir()
    files: dict[str, object] = {
        "manifest.json": {
            "schema_version": 1,
            "slug": "test-trail",
            "name": "Test Trail",
            "latitude": 18.5,
            "longitude": 73.8,
            "bbox": [18.4, 73.7, 18.6, 73.9],
            "timezone": "Asia/Kolkata",
            "fetched_at": "2026-10-07T05:00:00+00:00",
            "attribution": ["test data"],
        },
        "pois.json": {
            "pois": [
                {"name": "Viewpoint", "category": "tourism:viewpoint"},
                {"name": "Shelter", "category": "amenity:shelter"},
            ]
        },
        "elevation.json": {
            "points": [
                {"elevation_m": 610},
                {"elevation_m": 630},
                {"elevation_m": 620},
            ]
        },
        "sunrise_sunset.json": {
            "timezone": "Asia/Kolkata",
            "days": [
                {
                    "date": "2026-10-07",
                    "sunrise": "2026-10-07T06:20",
                    "sunset": "2026-10-07T18:10",
                }
            ],
        },
        "forecast.json": {
            "hourly": {
                "time": ["2026-10-07T11:00", "2026-10-07T12:00"],
                "temperature_2m": [25.0, 26.0],
                "precipitation_probability": [10, 20],
                "precipitation": [0.0, 0.0],
                "wind_speed_10m": [8.0, 10.0],
            }
        },
    }
    for name, value in files.items():
        (pack / name).write_text(json.dumps(value), encoding="utf-8")
    (pack / "route.gpx").write_text("<gpx version='1.1'/>", encoding="utf-8")
    (pack / "notes.md").write_text(
        "# Notes\n\n- Stay on the public marked trail.\n- Keep back from edges.\n",
        encoding="utf-8",
    )
    return LocationPack(pack)


def test_context_builder_uses_only_cached_pack_data(tmp_path: Path) -> None:
    pack = make_pack(tmp_path)
    context = ContextBuilder().build(
        pack,
        datetime(2026, 10, 7, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        UserConditions(slow=True),
    )

    assert context.place_name == "Test Trail"
    assert context.daylight
    assert context.daylight_remaining_min == 370
    assert context.elevation_m == 620
    assert context.nearby_pois == ("Viewpoint", "Shelter")
    assert context.slow
    assert not context.forecast_stale
    assert "Stay on the marked trail." in context.safety_reminders
    assert "slow pace" in context.narrator_text()


def test_user_reported_rain_overrides_dry_forecast(tmp_path: Path) -> None:
    context = ContextBuilder().build(
        make_pack(tmp_path),
        datetime(2026, 10, 7, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        UserConditions(rain=True, tired=True),
    )
    assert context.rain
    assert not context.quest_context().dry
    assert any("slippery" in reminder for reminder in context.safety_reminders)


def test_pack_fails_closed_when_required_file_is_missing(tmp_path: Path) -> None:
    directory = tmp_path / "incomplete"
    directory.mkdir()
    with pytest.raises(ValueError, match="incomplete location pack"):
        LocationPack(directory)
