# BirdNET integration

## Installation and offline boundary

Wild Quest pins `birdnet==1.1.1` and uses BirdNET 2.4 FP16 with the `tf` backend
and `library="litert"`. Despite the backend name, this path uses the lightweight
LiteRT interpreter included by the base BirdNET package on macOS ARM64/Python
3.11; TensorFlow is not installed.

Run this while online at home:

```sh
make setup
make bird-prefetch
```

The prefetch command downloads the model and 27 language label files into the
git-ignored `models/birdnet/` directory. `BIRDNET_APP_DATA` is configured before
BirdNET import because the library reads it at import time. At runtime Wild
Quest checks for the 25,932,528-byte FP16 model and all label files before model
load. Missing assets cause a local error with a prefetch instruction; runtime
code does not intentionally download anything.

The BirdNET source is MIT licensed, while the model is CC BY-NC-SA 4.0. That
model license includes a non-commercial restriction. Do not assume a commercial
Wild Quest release can ship or use the model without a licensing review.

## Quest and verification flow

The field flow is voice-first:

1. The existing safety guard must allow a configured bird quest.
2. Piper asks the user to remain at a safe stationary point on the marked trail.
3. Wild Quest records 12 seconds (configurable only within 10–15 seconds).
4. BirdNET analyzes 3-second segments, restricted to the curated 24-species
   Maharashtra/India list and the configured confidence threshold.
5. Every emitted detection, confidence, segment time, analysis threshold, and
   inference latency is written to SQLite.
6. Deterministic Python checks either the configured target label or whether a
   label is absent from prior SQLite history. It then submits typed `sensor`
   evidence to the state machine. BirdNET itself cannot complete a quest.
7. Piper speaks the result and describes detections as likely, not certain.

The default threshold is 0.25. Set `WILDQUEST_BIRD_CONFIDENCE` to tune it.
Lower values increase recall and false positives; threshold changes should be
evaluated against local field recordings before use.

## Public sample results

`tests/fixtures/birds/` contains four small public clips with a manifest,
checksums, source pages, authors, and licenses. Run `make bird-testset` online to
recreate it and `make bird-bench` offline to evaluate it.

Pinned BirdNET 2.4 FP16 results at threshold 0.25 on the M2:

| Clip label | Expected detected | Highest expected confidence |
| --- | ---: | ---: |
| Common Myna | No | below 0.25 (0.1146 at threshold 0.10) |
| Asian Koel | Yes | 0.9745 |
| House Crow | Yes | 0.9757 |
| Red-wattled Lapwing | Yes | 0.9998 |

This is 3/4 clip recall and 3/4 filtered top-1 accuracy (75%). Four clean public
clips are a smoke set, not a scientifically representative accuracy study. At
threshold 0.10, expected-species recall becomes 4/4, but Common Myna is ranked
below an incorrect Common Tailorbird detection, so the top-1 figure stays 3/4.

Median inference was 1.978 seconds in the threshold-0.25 run. The complete
post-recording result path on the Asian Koel clip took 2.589 seconds, comprising
2.311 seconds of BirdNET inference and 0.261 seconds of Piper synthesis. Model
and voice loading occur before recording. The 12-second recording itself is not
part of the “result ready” latency, so a full prompt/record/result interaction is
naturally longer than eight seconds.

The Wi-Fi-off microphone acceptance captured 10.645 seconds of WAV audio (the
FFmpeg/AVFoundation command occupied 13.408 seconds including startup), then
produced and audibly played the no-confident-detection response 1.863 seconds
after capture: 1.565 seconds BirdNET plus 0.281 seconds Piper synthesis.

## Limits and safe interpretation

- Wind, footsteps, speech, traffic, water, and microphone handling can mask or
  imitate calls. A sheltered microphone position helps, but never leave the
  trail to improve a recording.
- Overlapping species can cause missed detections or a confident wrong label.
  The model analyzes short windows and does not prove which individual called.
- Quiet, distant, juvenile, regional, or unusual calls may score below the
  threshold. “No detection” does not mean no bird was present.
- The curated list improves relevance but excludes many genuine visitors and
  migrants. An excluded species cannot be reported.
- Never approach, call to, feed, touch, or disturb birds or nests. Never move
  toward water, edges, traffic, or off-trail terrain for a stronger signal.
- BirdNET is not a safety sensor and has no authority over quest state outside
  the deterministic verifier.

Public sample sources: [Common Myna][myna], [Asian Koel][koel], [House Crow][crow],
and [Red-wattled Lapwing][lapwing].

[myna]: https://commons.wikimedia.org/wiki/File:CommonMynaCalls.ogg
[koel]: https://commons.wikimedia.org/wiki/File:Asian_Koel.ogg
[crow]: https://commons.wikimedia.org/wiki/File:Corvus_splendens.ogg
[lapwing]: https://commons.wikimedia.org/wiki/File:Redwattled_Lapwing.ogg
