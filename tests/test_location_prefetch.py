import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.prefetch_location import (
    TRAILS,
    extract_sun,
    parse_overpass,
    render_gpx,
    sample_coordinates,
)


def test_three_example_trails_are_supported() -> None:
    assert set(TRAILS) == {"sinhagad", "tamhini", "pashan-lake"}


def test_overpass_data_becomes_gpx_pois_and_samples() -> None:
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"highway": "path"},
                "geometry": [
                    {"lat": 18.1, "lon": 73.1},
                    {"lat": 18.2, "lon": 73.2},
                ],
            },
            {
                "type": "node",
                "id": 2,
                "lat": 18.2,
                "lon": 73.2,
                "tags": {"name": "Safe View", "tourism": "viewpoint"},
            },
        ]
    }
    tracks, pois = parse_overpass(payload)
    assert len(tracks) == 1
    assert pois[0]["name"] == "Safe View"
    assert sample_coordinates(tracks) == [(18.1, 73.1), (18.2, 73.2)]
    gpx = render_gpx(TRAILS["sinhagad"], tracks)
    assert ET.fromstring(gpx).tag.endswith("gpx")
    assert "not a verified route" in gpx


def test_sunrise_sunset_is_extracted_from_forecast() -> None:
    result = extract_sun(
        {
            "timezone": "Asia/Kolkata",
            "daily": {
                "time": ["2026-10-07"],
                "sunrise": ["2026-10-07T06:20"],
                "sunset": ["2026-10-07T18:10"],
            },
        }
    )
    assert result["days"] == [
        {
            "date": "2026-10-07",
            "sunrise": "2026-10-07T06:20",
            "sunset": "2026-10-07T18:10",
        }
    ]


def test_runtime_modules_contain_no_external_network_clients() -> None:
    root = Path(__file__).parents[1] / "wildquest"
    place_root = root / "place"
    network_clients = ("urllib", "requests", "httpx", "aiohttp")
    for path in place_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in network_clients), path
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "https://" not in source, path
