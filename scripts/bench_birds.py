#!/usr/bin/env python3
"""Measure BirdNET latency and clip-level accuracy on the public test set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

from wildquest.birds import BirdNetLiteRT


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/birds"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    classifier = BirdNetLiteRT(
        assets=ROOT / "models/birdnet",
        species_list=ROOT / "data/species/maharashtra_birdnet_v2.4.txt",
        threshold=args.threshold,
    )
    rows: list[dict[str, object]] = []
    for clip in manifest["clips"]:
        path = FIXTURES / clip["filename"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != clip["sha256"]:
            raise RuntimeError(f"checksum mismatch for {path}")
        analysis = classifier.analyze(path)
        labels = [detection.label for detection in analysis.detections]
        expected = clip["expected_label"]
        expected_detections = [
            detection
            for detection in analysis.detections
            if detection.label == expected
        ]
        row = {
            "filename": clip["filename"],
            "expected": expected,
            "top_label": labels[0] if labels else None,
            "top_confidence": (
                round(analysis.detections[0].confidence, 4)
                if analysis.detections
                else None
            ),
            "expected_max_confidence": (
                round(max(item.confidence for item in expected_detections), 4)
                if expected_detections
                else None
            ),
            "expected_detected": bool(expected_detections),
            "top1_correct": bool(labels and labels[0] == expected),
            "inference_s": round(analysis.inference_s, 3),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    clip_recall = sum(bool(row["expected_detected"]) for row in rows) / len(rows)
    top1_accuracy = sum(bool(row["top1_correct"]) for row in rows) / len(rows)
    summary = {
        "clips": len(rows),
        "threshold": args.threshold,
        "expected_species_clip_recall": clip_recall,
        "filtered_top1_accuracy": top1_accuracy,
        "median_inference_s": round(
            median(float(row["inference_s"]) for row in rows), 3
        ),
        "results": rows,
    }
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "bird_accuracy.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
