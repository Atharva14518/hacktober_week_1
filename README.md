# Wild Quest

Wild Quest is an offline, voice-only AI game master for hikes. Phase 0 proves the
local microphone → whisper.cpp → Ollama → Piper → earbuds loop on Apple Silicon.
No API keys, cloud APIs, or runtime downloads are used.

## Phase 0 quick start

Prerequisites: macOS on Apple Silicon, Xcode command-line tools, CMake, FFmpeg,
`uv`, and Ollama. The exact tested choices are in `docs/DECISIONS.md`.

```sh
make setup       # install locked Python dependencies and verify local tools
make prefetch    # the only networked step: download all model assets
make test
make run         # record 5 seconds, transcribe, narrate, and speak
make bench       # repeatable prerecorded-input benchmark
```

Run `OLLAMA_NO_CLOUD=1 ollama serve` in another terminal before `make run`.
Each turn writes stage latency to `data/wildquest.db`.

After `make prefetch`, disconnect Wi-Fi before `make run`. The smoke test talks
only to Ollama on loopback (`127.0.0.1`) and refuses to download missing assets.
If macOS asks, grant microphone access to the terminal application.

Configuration may be overridden with `WILDQUEST_LLM_MODEL`,
`WILDQUEST_WHISPER_MODEL`, and `WILDQUEST_PIPER_VOICE`. Defaults are selected for
the detected 8 GB M2 machine.

## Phase 2 quest engine

Thirty strictly validated quest definitions live in `data/quests/`. Quest state,
XP, streak, transition history, and LLM latency are persisted in SQLite. The
allowed lifecycle is:

```text
idle → offered → active → verifying → completed
                    ↘ active (failed verification)
offered/active/verifying → skipped or ended
```

An intent of `done` stops at `verifying`; only application code holding a typed
`VerificationEvidence` can complete a quest. Narration never changes state.

```sh
make test          # catalog, safety, persistence, crash resume, JSON fallback
make quest-smoke   # scripted conversation using local Qwen on Ollama loopback
```

`quest-smoke` writes its test state and per-call LLM timings to
`artifacts/phase2-smoke.db`. Runtime model output never connects to a remote URL.

## Phase 3 place awareness

Build location packs at home while online. The only network client for this
feature is `scripts/prefetch_location.py`; context building, adaptation, and
safety use local files and pure Python.

```sh
make prefetch-location TRAIL=sinhagad
make prefetch-location TRAIL=tamhini
make prefetch-location TRAIL=pashan-lake
```

Each pack contains a GPX snapshot of mapped walking ways, named OSM POIs,
elevation samples, seven days of sunrise/sunset and forecast data, and curated
safety notes. GPX ways are map data, not a verified or recommended route; signs,
closures, and local guidance always take precedence. Forecast-derived context
is marked stale when its nearest hourly sample is more than 90 minutes away.

After prefetching, disconnect Wi-Fi and run:

```sh
make place-demo TRAIL=sinhagad
uv run --locked python scripts/place_demo.py sinhagad --rain --tired
```

The deterministic adaptation engine shortens, eases, swaps, or ends quests for
rain, fatigue, low daylight, slow pace, and hard hazards. “I’m lost” and “I’m
hurt” are detected before LLM intent parsing: the active quest ends and the app
instructs the user to stop, stay put away from edges/water, and use the phone's
emergency call. Wild Quest explicitly does not present itself as an emergency
system.

## Phase 4 bird-call quests

Bird calls use BirdNET 2.4 FP16 through LiteRT on Apple Silicon. Model download
is part of prefetch; field inference has no network fallback.

```sh
make bird-prefetch       # online at home: download model + labels
make bird-testset        # online: attributed public acceptance clips
make bird-bench          # offline accuracy/latency report
make bird-run TRAIL=sinhagad  # offline 12-second microphone quest
```

The default confidence threshold is `0.25`; override it with
`WILDQUEST_BIRD_CONFIDENCE`. Detections, segment times, confidence, threshold,
and inference latency are written to SQLite. BirdNET supplies typed sensor
evidence, but only the Python state machine can complete the quest.

See `docs/BIRDNET.md` before field use. A detection is a likely machine
identification, not proof, and the model must never justify approaching birds,
nests, water, edges, or leaving the trail.
