#!/usr/bin/env python3
"""Download an attributed 20-image Wikimedia Commons vision acceptance set."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from wildquest.vision.images import normalize_image


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/vision"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "WildQuest/0.1 offline-vision-testset"
SAMPLES = (
    ("bird_01", "house sparrow bird", True),
    ("bird_02", "Indian peafowl bird", True),
    ("bird_03", "common myna bird", True),
    ("bird_04", "rose-ringed parakeet bird", True),
    ("bird_05", "red-vented bulbul bird", True),
    ("bird_06", "cattle egret bird", True),
    ("bird_07", "rock pigeon bird", True),
    ("bird_08", "black kite bird India", True),
    ("bird_09", "white-throated kingfisher bird", True),
    ("bird_10", "Asian koel bird", True),
    ("not_bird_01", "empty park bench", False),
    ("not_bird_02", "hiking backpack product", False),
    ("not_bird_03", "trail sign close up", False),
    ("not_bird_04", "waterfall landscape", False),
    ("not_bird_05", "mountain landscape", False),
    ("not_bird_06", "sunflower close up", False),
    ("not_bird_07", "tree trunk close up", False),
    ("not_bird_08", "empty forest footpath", False),
    ("not_bird_09", "lake landscape", False),
    ("not_bird_10", "granite boulder close up", False),
)


def request_json(parameters: dict[str, str]) -> dict[str, object]:
    url = API + "?" + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            time.sleep(1.5)
            return result
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable Wikimedia retry state")


def find_image(query: str) -> dict[str, object]:
    payload = request_json(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": "6",
            "gsrlimit": "1",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": "900",
        }
    )
    pages = payload.get("query", {}).get("pages", {})  # type: ignore[union-attr]
    if not pages:
        raise RuntimeError(f"no Wikimedia image found for {query!r}")
    return next(iter(pages.values()))


def metadata_value(info: dict[str, object], key: str) -> str:
    metadata = info.get("extmetadata", {})
    value = metadata.get(key, {}) if isinstance(metadata, dict) else {}
    return str(value.get("value", "")) if isinstance(value, dict) else ""


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for sample_id, query, expected in SAMPLES:
        page = find_image(query)
        info = page["imageinfo"][0]
        assert isinstance(info, dict)
        source_url = str(info.get("thumburl") or info["url"])
        request = urllib.request.Request(source_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        temporary = normalize_image(data, FIXTURES)
        path = FIXTURES / f"{sample_id}.jpg"
        temporary.replace(path)
        row = {
            "id": sample_id,
            "filename": path.name,
            "target": "a bird",
            "expected": expected,
            "query": query,
            "title": str(page["title"]),
            "source_page": str(info.get("descriptionurl", "")),
            "artist": metadata_value(info, "Artist"),
            "license": metadata_value(info, "LicenseShortName"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        rows.append(row)
        print(f"{sample_id}: {row['title']} ({row['license']})")
        write_manifest(rows)


def write_manifest(rows: list[dict[str, object]]) -> None:
    manifest = {
        "source": "Wikimedia Commons",
        "purpose": "small development acceptance set, not a general benchmark",
        "samples": rows,
    }
    (FIXTURES / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
