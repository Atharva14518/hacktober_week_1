#!/usr/bin/env python3
"""Measure strict-output accuracy, false positives, and latency on 20 images."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

from wildquest.vision.ollama import OllamaVisionClassifier


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/vision"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5vl:3b")
    parser.add_argument("--threshold", type=float, default=0.80)
    args = parser.parse_args()
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    classifier = OllamaVisionClassifier(args.model)
    rows: list[dict[str, object]] = []
    for sample in manifest["samples"]:
        path = FIXTURES / sample["filename"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
            raise RuntimeError(f"checksum mismatch for {path}")
        analysis = classifier.analyze(path, sample["target"])
        accepted = (
            analysis.parse_valid
            and analysis.answer.answer == "yes"
            and analysis.answer.confidence >= args.threshold
        )
        expected = bool(sample["expected"])
        row = {
            "id": sample["id"],
            "expected": expected,
            "answer": analysis.answer.answer,
            "confidence": analysis.answer.confidence,
            "accepted": accepted,
            "correct": accepted == expected,
            "parse_valid": analysis.parse_valid,
            "attempts": analysis.attempts,
            "first_token_s": round(analysis.first_token_s, 3),
            "total_s": round(analysis.total_s, 3),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    negatives = [row for row in rows if not bool(row["expected"])]
    positives = [row for row in rows if bool(row["expected"])]
    summary = {
        "model": args.model,
        "samples": len(rows),
        "threshold": args.threshold,
        "accuracy": sum(bool(row["correct"]) for row in rows) / len(rows),
        "false_positive_rate": sum(bool(row["accepted"]) for row in negatives)
        / len(negatives),
        "true_positive_rate": sum(bool(row["accepted"]) for row in positives)
        / len(positives),
        "invalid_json_rate": sum(not bool(row["parse_valid"]) for row in rows)
        / len(rows),
        "median_first_token_s": median(float(row["first_token_s"]) for row in rows),
        "median_total_s": median(float(row["total_s"]) for row in rows),
        "results": rows,
    }
    output = ROOT / "artifacts" / f"vision_accuracy_{args.model.replace(':', '_')}.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
