"""Compact offline place context assembled from cached pack data."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from wildquest.place.pack import LocationPack
from wildquest.quests.models import PlaceContext
from wildquest.safety.incidents import SafetyAdvisor


class UserConditions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rain: bool = False
    tired: bool = False
    slow: bool = False
    on_marked_trail: bool = True
    near_edge: bool = False
    near_water: bool = False


class OfflineContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    place_name: str
    local_time: str
    daylight: bool
    daylight_remaining_min: int = Field(ge=0)
    rain: bool
    tired: bool
    slow: bool
    on_marked_trail: bool
    near_edge: bool
    near_water: bool
    temperature_c: float | None
    precipitation_probability: int | None
    wind_speed_kmh: float | None
    elevation_m: int | None
    nearby_pois: tuple[str, ...]
    trail_notes: tuple[str, ...]
    safety_reminders: tuple[str, ...]
    forecast_stale: bool

    def narrator_text(self) -> str:
        conditions = ["rain" if self.rain else "dry"]
        if self.tired:
            conditions.append("user tired")
        if self.slow:
            conditions.append("slow pace")
        weather = ", ".join(conditions)
        poi_text = ", ".join(self.nearby_pois[:3]) or "no named POIs nearby"
        reminder = " ".join(self.safety_reminders)
        elevation = str(self.elevation_m) if self.elevation_m is not None else "unknown"
        return (
            f"Place: {self.place_name}. Local time: {self.local_time}. "
            f"Daylight remaining: {self.daylight_remaining_min} minutes. "
            f"Conditions: {weather}. Elevation: {elevation} m. "
            f"Nearby: {poi_text}. Safety: {reminder}"
        )

    def quest_context(self) -> PlaceContext:
        return PlaceContext(
            place_name=self.place_name,
            daylight=self.daylight,
            dry=not self.rain,
            on_marked_trail=self.on_marked_trail,
            good_visibility=not self.rain,
            low_wind=self.wind_speed_kmh is None or self.wind_speed_kmh < 30,
            near_edge=self.near_edge,
            near_water=self.near_water,
            weather_note="rain" if self.rain else "dry conditions",
        )


class ContextBuilder:
    def __init__(self, advisor: SafetyAdvisor | None = None) -> None:
        self.advisor = advisor or SafetyAdvisor()

    def build(
        self, pack: LocationPack, at: datetime, conditions: UserConditions
    ) -> OfflineContext:
        if at.tzinfo is None:
            raise ValueError("context time must be timezone-aware")
        local = at.astimezone(ZoneInfo(pack.manifest.timezone))
        sunrise, sunset = _sun_window(pack.sun, local)
        daylight = sunrise <= local < sunset
        remaining = max(0, int((sunset - local).total_seconds() // 60)) if daylight else 0
        weather, stale = _nearest_weather(pack.forecast, local)
        forecast_rain = float(weather.get("precipitation", 0) or 0) > 0
        reported_rain = conditions.rain or forecast_rain
        elevation = _median_elevation(pack.elevation)
        poi_names = _poi_names(pack.pois)
        reminders = self.advisor.reminders(
            rain=reported_rain,
            tired=conditions.tired,
            slow=conditions.slow,
            daylight_remaining_min=remaining,
            daylight=daylight,
        )
        return OfflineContext(
            place_name=pack.manifest.name,
            local_time=local.isoformat(timespec="minutes"),
            daylight=daylight,
            daylight_remaining_min=remaining,
            rain=reported_rain,
            tired=conditions.tired,
            slow=conditions.slow,
            on_marked_trail=conditions.on_marked_trail,
            near_edge=conditions.near_edge,
            near_water=conditions.near_water,
            temperature_c=_optional_float(weather.get("temperature_2m")),
            precipitation_probability=_optional_int(
                weather.get("precipitation_probability")
            ),
            wind_speed_kmh=_optional_float(weather.get("wind_speed_10m")),
            elevation_m=elevation,
            nearby_pois=poi_names,
            trail_notes=pack.notes[:4],
            safety_reminders=reminders,
            forecast_stale=stale,
        )


def _sun_window(data: dict[str, object], local: datetime) -> tuple[datetime, datetime]:
    days = data.get("days")
    if not isinstance(days, list):
        raise ValueError("sunrise_sunset.json has no days list")
    target = local.date().isoformat()
    for item in days:
        if isinstance(item, dict) and item.get("date") == target:
            sunrise = datetime.fromisoformat(str(item["sunrise"]))
            sunset = datetime.fromisoformat(str(item["sunset"]))
            zone = local.tzinfo
            return sunrise.replace(tzinfo=zone), sunset.replace(tzinfo=zone)
    raise ValueError(f"location pack has no sun data for {target}")


def _nearest_weather(
    data: dict[str, object], local: datetime
) -> tuple[dict[str, Any], bool]:
    hourly = data.get("hourly")
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        raise ValueError("forecast.json has no hourly time series")
    times = [
        datetime.fromisoformat(str(value)).replace(tzinfo=local.tzinfo)
        for value in hourly["time"]
    ]
    if not times:
        raise ValueError("forecast hourly time series is empty")
    index = min(range(len(times)), key=lambda item: abs((times[item] - local).total_seconds()))
    row: dict[str, Any] = {}
    for key, values in hourly.items():
        if key != "time" and isinstance(values, list) and index < len(values):
            row[key] = values[index]
    stale = abs((times[index] - local).total_seconds()) > 5400
    return row, stale


def _median_elevation(data: dict[str, object]) -> int | None:
    points = data.get("points")
    if not isinstance(points, list):
        return None
    values = sorted(
        float(point["elevation_m"])
        for point in points
        if isinstance(point, dict) and point.get("elevation_m") is not None
    )
    if not values:
        return None
    return round(values[len(values) // 2])


def _poi_names(data: dict[str, object]) -> tuple[str, ...]:
    pois = data.get("pois")
    if not isinstance(pois, list):
        return ()
    names: list[str] = []
    for poi in pois:
        if isinstance(poi, dict) and isinstance(poi.get("name"), str):
            name = poi["name"].strip()
            if name and name not in names:
                names.append(name)
    return tuple(names[:5])


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _optional_int(value: object) -> int | None:
    return round(float(value)) if isinstance(value, (int, float)) else None
