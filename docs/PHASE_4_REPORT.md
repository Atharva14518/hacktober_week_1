# Phase 4 report — 2026-10-07

## What works

- BirdNET 2.4 FP16 runs through LiteRT on the Apple M2 without TensorFlow and
  without runtime network access. Model/label acquisition is part of the online
  prefetch command and incomplete assets fail closed.
- Two bird quests cover a configured Common Myna target and any species not
  previously detected in SQLite. The filter contains 24 curated common
  Maharashtra/India BirdNET labels; confidence defaults to 0.25.
- A 10–15-second microphone recorder, reusable preloaded classifier, SQLite
  detection log, state-machine verifier, and Piper spoken result form the full
  voice-first path.
- BirdNET cannot complete quests directly. It produces typed sensor evidence;
  deterministic Python compares exact labels/history and the existing state
  machine remains the only component that awards completion and XP.

## Tests, accuracy, and latency

All 55 tests pass, including target rejection, any-new-species history, SQLite
confidence persistence, strict config validation, and real inference over four
attributed public clips.

At threshold 0.25 the expected species was detected in 3/4 clips and was the
top filtered result in 3/4 clips (75%). Common Myna was the miss. Threshold 0.10
raised expected-species recall to 4/4 but incorrectly ranked Common Tailorbird
above Common Myna, leaving top-1 accuracy at 3/4. These four clips are a smoke
set, not a population-level accuracy estimate.

Median public-clip inference was 1.978 seconds. The complete result-ready path
on the Asian Koel clip was 2.589 seconds after recording: 2.311 seconds BirdNET
and 0.261 seconds Piper synthesis. It completed the any-new-species quest and
persisted three segment detections at 0.9745, 0.9247, and 0.8708 confidence.

The final acceptance ran with macOS reporting Wi-Fi off. A real microphone
capture produced 10.645 seconds of audio; the command took 13.408 seconds with
AVFoundation startup. BirdNET found no listed species above 0.25, correctly left
the quest active, synthesized the cautious retry response, and played it aloud.
Result-ready latency was 1.863 seconds: 1.565 seconds BirdNET and 0.281 seconds
Piper. The complete 55-test suite then passed before Wi-Fi was restored.

## Known issues

- Wind and overlapping calls materially reduce reliability. Traffic, speech,
  water, footsteps, and microphone handling are additional confounders.
- The curated list intentionally excludes many valid Indian species; excluded
  birds cannot be identified. Seasonal/local lists need field validation.
- BirdNET model licensing is CC BY-NC-SA 4.0 and needs review before any
  commercial use. Model output is always phrased as a likely identification.
- The ~8-second target is measured from recording completion until spoken audio
  is ready. A required 10–15-second recording makes the whole interaction longer.
