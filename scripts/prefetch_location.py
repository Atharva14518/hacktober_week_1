#!/usr/bin/env python3
"""Build a complete location pack while an internet connection is available.

This is deliberately the only module in the place-awareness feature that
imports a network client. Runtime code reads the generated files only.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
USER_AGENT = "WildQuest/0.1 (offline location-pack prefetch)"


@dataclass(frozen=True)
class TrailDefinition:
    slug: str
    name: str
    latitude: float
    longitude: float
    bbox: tuple[float, float, float, float]
    timezone: str
    notes: tuple[str, ...]


TRAILS = {
    trail.slug: trail
    for trail in (
        TrailDefinition(
            slug="sinhagad",
            name="Sinhagad Fort",
            latitude=18.3663,
            longitude=73.7559,
            bbox=(18.337, 73.729, 18.392, 73.782),
            timezone="Asia/Kolkata",
            notes=(
                "Use established walking routes and obey local closures and signs.",
                "Fort walls, cliffs, and exposed viewpoints require extra distance from edges.",
                "Monsoon rain can make stone and soil slippery; skip movement quests when wet.",
                "Carry drinking water; never treat a mapped water feature as potable.",
            ),
        ),
        TrailDefinition(
            slug="tamhini",
            name="Tamhini Ghat",
            latitude=18.4810,
            longitude=73.4170,
            bbox=(18.445, 73.380, 18.505, 73.455),
            timezone="Asia/Kolkata",
            notes=(
                "Stay on a signed public route; this broad area includes roads and private land.",
                "Rain, mist, and fast water can change conditions quickly in monsoon season.",
                "Keep well away from waterfalls, streams, road edges, and steep drops.",
                "Turn around early if visibility or daylight is decreasing.",
            ),
        ),
        TrailDefinition(
            slug="pashan-lake",
            name="Pashan Lake",
            latitude=18.5360,
            longitude=73.7860,
            bbox=(18.525, 73.772, 18.546, 73.800),
            timezone="Asia/Kolkata",
            notes=(
                "Use open public paths and follow posted access hours and local signs.",
                "Keep back from the shoreline and never enter the water for a quest.",
                "Observe birds and other wildlife quietly without feeding, touching, or approaching.",
                "Skip a quest if a path is muddy, flooded, closed, or poorly lit.",
            ),
        ),
    )
}


def fetch_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
    attempts: int = 3,
) -> dict[str, Any]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = urllib.parse.urlencode(form).encode() if form else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object from {url}")
            return value
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"request failed after {attempts} attempts: {url}") from last_error


def overpass_query(trail: TrailDefinition) -> str:
    south, west, north, east = trail.bbox
    bbox = f"{south},{west},{north},{east}"
    return f"""[out:json][timeout:60];
(
  way[\"highway\"~\"^(path|footway|track|steps)$\"]({bbox});
  nwr[\"tourism\"~\"^(viewpoint|picnic_site|information)$\"]({bbox});
  nwr[\"amenity\"~\"^(shelter|drinking_water|toilets|parking)$\"]({bbox});
  nwr[\"historic\"]({bbox});
  nwr[\"natural\"~\"^(peak|cave_entrance|water|wood)$\"]({bbox});
);
out body geom qt;"""


def parse_overpass(
    payload: dict[str, Any],
) -> tuple[list[list[tuple[float, float]]], list[dict[str, object]]]:
    tracks: list[list[tuple[float, float]]] = []
    pois: list[dict[str, object]] = []
    elements = payload.get("elements", [])
    if not isinstance(elements, list):
        raise ValueError("Overpass response has no elements list")
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        tags = tags if isinstance(tags, dict) else {}
        geometry = element.get("geometry")
        points = _geometry_points(geometry)
        if element.get("type") == "way" and tags.get("highway") and len(points) >= 2:
            tracks.append(points)
            continue
        name = tags.get("name") or tags.get("name:en")
        category = _poi_category(tags)
        coordinates = _element_coordinates(element, points)
        if isinstance(name, str) and category and coordinates:
            latitude, longitude = coordinates
            pois.append(
                {
                    "name": name,
                    "category": category,
                    "latitude": latitude,
                    "longitude": longitude,
                    "osm_type": element.get("type"),
                    "osm_id": element.get("id"),
                }
            )
    pois.sort(key=lambda item: (str(item["category"]), str(item["name"])))
    return tracks, pois


def _geometry_points(value: object) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        return []
    points: list[tuple[float, float]] = []
    for point in value:
        if isinstance(point, dict) and isinstance(point.get("lat"), (int, float)) and isinstance(
            point.get("lon"), (int, float)
        ):
            points.append((float(point["lat"]), float(point["lon"])))
    return points


def _element_coordinates(
    element: dict[str, Any], points: list[tuple[float, float]]
) -> tuple[float, float] | None:
    if isinstance(element.get("lat"), (int, float)) and isinstance(
        element.get("lon"), (int, float)
    ):
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and isinstance(center.get("lat"), (int, float)) and isinstance(
        center.get("lon"), (int, float)
    ):
        return float(center["lat"]), float(center["lon"])
    if points:
        return (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
    return None


def _poi_category(tags: dict[str, Any]) -> str | None:
    for key in ("tourism", "amenity", "historic", "natural"):
        if key in tags:
            return f"{key}:{tags[key]}"
    return None


def sample_coordinates(
    tracks: list[list[tuple[float, float]]], limit: int = 80
) -> list[tuple[float, float]]:
    flattened = [point for track in tracks for point in track]
    if not flattened:
        return []
    if len(flattened) <= limit:
        return flattened
    return [
        flattened[round(index * (len(flattened) - 1) / (limit - 1))]
        for index in range(limit)
    ]


def render_gpx(trail: TrailDefinition, tracks: list[list[tuple[float, float]]]) -> str:
    ET.register_namespace("", "http://www.topografix.com/GPX/1/1")
    root = ET.Element(
        "{http://www.topografix.com/GPX/1/1}gpx",
        {"version": "1.1", "creator": "Wild Quest location prefetch"},
    )
    metadata = ET.SubElement(root, "{http://www.topografix.com/GPX/1/1}metadata")
    ET.SubElement(metadata, "{http://www.topografix.com/GPX/1/1}name").text = trail.name
    track = ET.SubElement(root, "{http://www.topografix.com/GPX/1/1}trk")
    ET.SubElement(track, "{http://www.topografix.com/GPX/1/1}name").text = (
        f"Mapped walking ways near {trail.name}; not a verified route"
    )
    for points in tracks:
        segment = ET.SubElement(track, "{http://www.topografix.com/GPX/1/1}trkseg")
        for latitude, longitude in points:
            ET.SubElement(
                segment,
                "{http://www.topografix.com/GPX/1/1}trkpt",
                {"lat": str(latitude), "lon": str(longitude)},
            )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def build_pack(trail: TrailDefinition, output_root: Path) -> Path:
    print(f"Fetching mapped ways and POIs for {trail.name}...")
    osm = fetch_json(OVERPASS_URL, form={"data": overpass_query(trail)})
    tracks, pois = parse_overpass(osm)
    samples = sample_coordinates(tracks)
    if not samples:
        raise RuntimeError("Overpass returned no mapped walking ways; refusing an empty pack")

    print(f"Fetching elevation for {len(samples)} route samples...")
    elevation = fetch_json(
        ELEVATION_URL,
        params={
            "latitude": ",".join(str(point[0]) for point in samples),
            "longitude": ",".join(str(point[1]) for point in samples),
        },
    )
    elevations = elevation.get("elevation")
    if not isinstance(elevations, list) or len(elevations) != len(samples):
        raise RuntimeError("Open-Meteo returned incomplete elevation samples")

    print("Fetching seven-day forecast and sunrise/sunset...")
    forecast = fetch_json(
        FORECAST_URL,
        params={
            "latitude": str(trail.latitude),
            "longitude": str(trail.longitude),
            "timezone": trail.timezone,
            "forecast_days": "7",
            "hourly": (
                "temperature_2m,precipitation_probability,precipitation,"
                "weather_code,wind_speed_10m"
            ),
            "daily": "sunrise,sunset,precipitation_probability_max",
        },
    )
    sun = extract_sun(forecast)

    directory = output_root / trail.slug
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(
        directory / "manifest.json",
        {
            "schema_version": 1,
            "slug": trail.slug,
            "name": trail.name,
            "latitude": trail.latitude,
            "longitude": trail.longitude,
            "bbox": trail.bbox,
            "timezone": trail.timezone,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "attribution": (
                "© OpenStreetMap contributors, ODbL",
                "Weather data by Open-Meteo",
                "Elevation data: Copernicus DEM via Open-Meteo",
            ),
        },
    )
    (directory / "route.gpx").write_text(render_gpx(trail, tracks), encoding="utf-8")
    _write_json(directory / "pois.json", {"pois": pois})
    _write_json(
        directory / "elevation.json",
        {
            "points": [
                {"latitude": lat, "longitude": lon, "elevation_m": height}
                for (lat, lon), height in zip(samples, elevations, strict=True)
            ]
        },
    )
    _write_json(directory / "sunrise_sunset.json", sun)
    _write_json(directory / "forecast.json", forecast)
    notes = [f"# {trail.name} curated notes", "", *(f"- {note}" for note in trail.notes)]
    notes.extend(
        [
            "",
            "Route data is a snapshot of mapped walking ways, not a verified or recommended trail.",
            "Attribution: © OpenStreetMap contributors (ODbL); Open-Meteo; Copernicus DEM.",
            "",
        ]
    )
    (directory / "notes.md").write_text("\n".join(notes), encoding="utf-8")
    print(f"Saved {len(tracks)} way segments and {len(pois)} named POIs to {directory}")
    return directory


def extract_sun(forecast: dict[str, Any]) -> dict[str, object]:
    daily = forecast.get("daily")
    if not isinstance(daily, dict):
        raise RuntimeError("Open-Meteo response has no daily data")
    dates = daily.get("time")
    sunrises = daily.get("sunrise")
    sunsets = daily.get("sunset")
    if not all(isinstance(value, list) for value in (dates, sunrises, sunsets)):
        raise RuntimeError("Open-Meteo response has incomplete sunrise/sunset data")
    if not (len(dates) == len(sunrises) == len(sunsets)):
        raise RuntimeError("Open-Meteo sunrise/sunset arrays do not align")
    return {
        "timezone": forecast.get("timezone"),
        "days": [
            {"date": date, "sunrise": sunrise, "sunset": sunset}
            for date, sunrise, sunset in zip(dates, sunrises, sunsets, strict=True)
        ],
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trail", nargs="?", choices=sorted(TRAILS))
    parser.add_argument("--all", action="store_true", help="prefetch all example trails")
    parser.add_argument("--list", action="store_true", help="list supported trail slugs")
    parser.add_argument(
        "--output-root", type=Path, default=Path("data/location_packs")
    )
    args = parser.parse_args()
    if not (args.list or args.all or args.trail):
        parser.error("provide a trail slug, --all, or --list")
    return args


def main() -> int:
    args = parse_args()
    if args.list:
        for slug, trail in TRAILS.items():
            print(f"{slug}: {trail.name}")
        return 0
    selected = list(TRAILS.values()) if args.all else [TRAILS[args.trail]]
    for trail in selected:
        build_pack(trail, args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
