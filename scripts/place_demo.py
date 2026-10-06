#!/usr/bin/env python3
"""Build offline context and adapt one quest from an already-prefetched pack."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from wildquest.place import AdaptationEngine, ContextBuilder, LocationPack, UserConditions
from wildquest.quests.models import load_quests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trail", help="location pack slug, for example sinhagad")
    parser.add_argument("--quest", default="gentle-incline-rhythm")
    parser.add_argument("--rain", action="store_true")
    parser.add_argument("--tired", action="store_true")
    parser.add_argument("--slow", action="store_true")
    parser.add_argument("--off-trail", action="store_true")
    parser.add_argument("--near-edge", action="store_true")
    parser.add_argument("--near-water", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    pack = LocationPack(Path("data/location_packs") / args.trail)
    now = datetime.now(ZoneInfo(pack.manifest.timezone))
    context = ContextBuilder().build(
        pack,
        now,
        UserConditions(
            rain=args.rain,
            tired=args.tired,
            slow=args.slow,
            on_marked_trail=not args.off_trail,
            near_edge=args.near_edge,
            near_water=args.near_water,
        ),
    )
    quests = load_quests(Path("data/quests"))
    decision = AdaptationEngine(quests).adapt(quests[args.quest], context)
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(context.narrator_text())
    print(
        json.dumps(
            {
                "action": decision.action.value,
                "selected_quest": (
                    decision.selected_quest.id if decision.selected_quest else None
                ),
                "duration_min": (
                    decision.selected_quest.duration_min
                    if decision.selected_quest
                    else None
                ),
                "reasons": decision.reasons,
                "offline_context_and_adaptation_ms": round(elapsed_ms, 2),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
