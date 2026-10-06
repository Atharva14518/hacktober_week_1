#!/usr/bin/env python3
"""Download the small attributed public BirdNET acceptance set."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/birds"


@dataclass(frozen=True)
class PublicClip:
    filename: str
    commons_title: str
    expected_label: str
    author: str
    license: str

    @property
    def source_page(self) -> str:
        title = urllib.parse.quote(self.commons_title.replace(" ", "_"))
        return f"https://commons.wikimedia.org/wiki/File:{title}"

    @property
    def download_url(self) -> str:
        title = urllib.parse.quote(self.commons_title)
        return f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{title}"


CLIPS = (
    PublicClip(
        "common_myna.ogg",
        "CommonMynaCalls.ogg",
        "Acridotheres tristis_Common Myna",
        "L. Shyamal",
        "CC BY-SA 2.5",
    ),
    PublicClip(
        "asian_koel.ogg",
        "Asian Koel.ogg",
        "Eudynamys scolopaceus_Asian Koel",
        "Philip Eapen",
        "CC BY-SA 4.0",
    ),
    PublicClip(
        "house_crow.ogg",
        "Corvus splendens.ogg",
        "Corvus splendens_House Crow",
        "Vladimir Yu. Arkhipov",
        "CC BY-SA 3.0",
    ),
    PublicClip(
        "red_wattled_lapwing.ogg",
        "Redwattled Lapwing.ogg",
        "Vanellus indicus_Red-wattled Lapwing",
        "Gypsypkd",
        "Public domain",
    ),
)


def download(clip: PublicClip) -> bytes:
    request = urllib.request.Request(
        clip.download_url,
        headers={
            "User-Agent": "WildQuest/0.1 (offline hiking game; test dataset prefetch)"
        },
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metadata: list[dict[str, object]] = []
    for clip in CLIPS:
        path = OUTPUT / clip.filename
        if not path.exists():
            print(f"Downloading {clip.commons_title}...", flush=True)
            path.write_bytes(download(clip))
            time.sleep(2)
        values = asdict(clip)
        values.update(
            {
                "source_page": clip.source_page,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
        metadata.append(values)
    (OUTPUT / "manifest.json").write_text(
        json.dumps({"clips": metadata}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Public test set ready: {len(CLIPS)} clips in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
