# Phase 5 report — vision quests

Date: 2026-10-07  
Hardware: MacBook Air (Mac14,2), Apple M2, 8 CPU cores, 8 GB unified memory  
Runtime: Ollama 0.40.0, local loopback only

## What works

- Two photo quests are available: a bird and a trail marker/sign. The safety
  gate still requires daylight, a marked trail, visibility, and level ground.
- A Mac webcam frame can be captured through FFmpeg/AVFoundation. A phone can
  instead upload JPEG, PNG, or WebP through a tokenized FastAPI page reachable
  over a local hotspot with no internet connection.
- Uploaded content is limited to 10 MiB and 25 megapixels, decoded with Pillow,
  metadata-stripped, resized, and written to a generated local filename.
- Ollama receives only a 512 px inference copy and returns a JSON-schema-
  constrained yes/no answer plus confidence. Pydantic forbids extra fields and
  coercion. Invalid output retries once and then safely becomes `no/0.0`.
- A positive result must meet the quest threshold. The service logs the model,
  answer, confidence, threshold, JSON validity, attempts, first-token time,
  total time, and gate result to SQLite. It then submits typed sensor evidence
  to the state machine; the VLM cannot mutate quest state.
- A failed attempt leaves the quest active. An explicit “trust me” confirmation
  is available only after that logged failure and prevents a dead end.
- Eating/tasting/foraging/poison/medicinal image targets are rejected in Python
  before inference. Wild Quest does not identify plants or animals for eating.

## Model decision and measured results

The development set contains 20 visually checked Wikimedia Commons images:
10 clear birds and 10 non-bird scenes/objects. Each file has a source page,
license, attribution, and SHA-256 checksum in
`tests/fixtures/vision/manifest.json`. The question was “does this image show a
bird?” and the acceptance threshold was 0.80.

| Model | Size | Accuracy | False-positive rate | True-positive rate | Invalid JSON | Median first token | Median total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5-VL 3B Q4_K_M | 3.2 GB | 20/20 (100%) | 0/10 (0%) | 10/10 (100%) | 0/20 | 25.776 s | 27.118 s |
| Moondream 1.8B | 1.7 GB | 10/20 (50%) | 0/10 (0%) | 0/10 (0%) | 0/20 | 1.995 s | 2.173 s |

Qwen2.5-VL 3B is selected. Moondream was much faster, but under the required
schema it returned the same `no`/0.8 response for all 20 images and therefore
could not verify a real positive. Qwen followed the schema and separated every
image in this small set, but its measured latency is poor on an 8 GB M2 because
Ollama reports a mixed CPU/GPU load. Correctness wins for a verification gate;
the player can hear a short waiting prompt in a later UX phase.

The 0% Qwen false-positive rate is **0 of only 10 negatives**, not proof of a
zero population rate. Its approximate 95% “rule of three” upper bound is 30%.
The set is curated, public, restricted to an easy bird/non-bird question, and
may overlap model training data. It does not establish performance for small,
occluded, distant, night, trail-marker, or adversarial images. Qwen also emitted
0.99 for every answer, so its self-reported confidence is plainly not calibrated;
the threshold is a conservative policy gate, not a probability guarantee.

Raw generated results are written locally (and intentionally gitignored) as
`artifacts/vision_accuracy_qwen2.5vl_3b.json` and
`artifacts/vision_accuracy_moondream_1.8b.json`.

## Offline acceptance

- Model files and the test corpus were prefetched through the only networked
  scripts: `scripts/prefetch_models.py` and
  `scripts/prefetch_vision_samples.py`.
- Inference uses only `http://127.0.0.1:11434`; phone upload binds to the local
  interface and performs no outbound requests.
- The benchmark and application paths have no runtime downloader or API key.
- Automated suite: 70 tests pass in 9.89 s.
- End-to-end offline acceptance on a previously benchmarked bird image completed
  the state machine and produced local Piper speech: VLM first token 1.251 s,
  VLM total 2.532 s, TTS 0.275 s, result ready 3.710 s. This warm/cached example
  is not representative of new-image latency; the 27.118 s benchmark median is
  the honest field-planning number.

## Known issues

- Qwen's roughly 27 s median result time misses the desired conversational feel
  on this 8 GB laptop. A future phase should benchmark a newer 2B-class VLM or
  a native MLX-VLM route on the same held-out images before changing runtimes.
- The acceptance corpus is too small and narrow to tune a reliable threshold.
  Add locally photographed, held-out trail-marker, distant-bird, empty-canopy,
  blur, low-light, and partial-object negatives before field release.
- The FastAPI link is bearer-token protected but plain HTTP on the local
  hotspot. Use it only on a trusted personal hotspot and stop the server after
  the upload.
- Webcam device numbering depends on AVFoundation enumeration. The CLI exposes
  `--camera-device`; macOS camera permission must be granted to the terminal.
- A VLM result must never be treated as species identification, edibility
  advice, route guidance, or emergency guidance.
