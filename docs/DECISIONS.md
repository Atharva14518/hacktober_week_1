# Architecture decisions

## 2026-10-07 — Phase 0 hardware and model selection

`system_profiler SPHardwareDataType` was run before model selection. Target:
MacBook Air `Mac14,2`, Apple M2 (8 cores: 4 performance + 4 efficiency), 8 GB
unified memory, macOS 27.0.1.

- LLM baseline: `qwen2.5:3b-instruct` (`Q4_K_M`, 1.9 GB). This is the default
  because it leaves headroom for whisper.cpp, Piper, Python, and macOS. Tested
  Ollama content ID: `357c53fb659c`.
- LLM comparison: `gemma3:4b-it-q4_K_M` (3.3 GB). It is installed for quality
  and latency comparison but is run separately, never concurrently with Qwen.
  Tested Ollama content ID: `a2af6cc3eb7f`.
- STT: multilingual whisper.cpp `base` (142 MiB) is the default; `small`
  (466 MiB) is installed for accuracy comparison. whisper.cpp v1.9.4 is built
  natively with CMake; Metal is enabled by default on Apple Silicon.
- TTS baseline: Piper 1.8.0 with `en_US-lessac-medium`, selected for low memory,
  predictable local inference, and a maintained macOS wheel.
- TTS alternative: `kokoro-onnx==0.6.1` with Kokoro 82M v1.0 FP16 (164 MB) is
  evaluated separately. Piper remains the Phase 0 path because it is smaller
  and operationally simpler on an 8 GB machine. Kokoro is not placed on the
  critical smoke-test path and macOS uses its CPU ONNX provider.
- Python: CPython 3.11, managed by uv; all direct Python dependencies are exact
  pins in `pyproject.toml`, and all transitive versions are locked in `uv.lock`.
  The preinstalled uv is 0.5.3. Current documentation mentions
  `uv lock --check`, but that flag is not present in 0.5.3, so Phase 0 verifies
  consistency with the supported equivalent `uv sync --locked`.
- Runtime network boundary: model acquisition is confined to
  `scripts/prefetch_models.py`. The runtime requires assets to exist locally and
  only uses Ollama's loopback HTTP endpoint.
- Latency persistence: each smoke-test turn writes record, STT, LLM first-token,
  LLM total, TTS, and end-to-end durations to SQLite `data/wildquest.db`.


Official sources checked before installation: [Astral uv projects][uv],
[Ollama's macOS README][ollama], the Ollama [Qwen][qwen] and [Gemma][gemma]
libraries, [ggml-org whisper.cpp][whisper], [OHF-Voice Piper][piper], and
[Kokoro ONNX][kokoro]. On Apple Silicon, whisper.cpp uses Metal automatically;
Piper and Kokoro use CPU ONNX Runtime wheels.

[uv]: https://docs.astral.sh/uv/guides/projects/
[ollama]: https://github.com/ollama/ollama/blob/main/README.md
[qwen]: https://ollama.com/library/qwen2.5/tags
[gemma]: https://ollama.com/library/gemma3/tags
[whisper]: https://github.com/ggml-org/whisper.cpp
[piper]: https://github.com/OHF-Voice/piper1-gpl
[kokoro]: https://github.com/thewh1teagle/kokoro-onnx

## 2026-10-07 — Phase 2 quest engine

- Quest files are loaded with `yaml.safe_load` and validated by
  `pydantic==2.13.5`; unknown fields and invalid enum values fail closed.
  `pyyaml==6.0.3` and Pydantic are exact direct pins, with transitive versions in
  `uv.lock`. Both provide native Apple Silicon-compatible wheels for Python 3.11.
- SQLite plus the Python state machine are authoritative. The database stores
  the current run, optimistic version, every transition, XP, streak, and LLM
  timings. Reopening the database reconstructs the last persisted state.
- An LLM `done` intent means only “the user claims to be done” and transitions
  `active → verifying`. Completion requires a separate strict
  `VerificationEvidence` whose source is limited to timer, sensor, photo
  metadata, or application-level user confirmation.
- XP is 10/20/30 for easy/moderate/challenging quests, plus two XP per existing
  streak step capped at five. Completion increments streak; skip/end resets it.
- Intent output is exactly `{"intent": <enum>}` with extra fields forbidden.
  Parsing retries once, then applies an offline keyword fallback. Narrator text
  has no state authority and passes through code-level unsafe-language override.
- Safety gating is independent of prompts. All quests require daylight and a
  marked trail; global rules also block offers off-trail, near edges, near water,
  or after dark. Quest-specific conditions such as dry ground and visibility are
  checked before an offer.

Official sources checked before dependency installation: [Pydantic JSON
validation][pydantic-json], [Pydantic package releases][pydantic-pypi], and the
[PyYAML project guidance][pyyaml] recommending `safe_load` for untrusted input.

[pydantic-json]: https://docs.pydantic.dev/latest/concepts/json/
[pydantic-pypi]: https://pypi.org/project/pydantic/
[pyyaml]: https://github.com/yaml/pyyaml/blob/main/README.md

## 2026-10-07 — Phase 3 place awareness and adaptation

- Location acquisition is confined to `scripts/prefetch_location.py`. It uses
  Python's standard library, so Phase 3 adds no dependency or Apple Silicon
  compatibility burden. Runtime modules do not import HTTP clients.
- Each pack is complete only when its manifest, GPX, POIs, elevation,
  sunrise/sunset, forecast, and curated notes files exist. Loading fails closed
  if any are missing. The GPX contains nearby OSM walking ways and is labelled
  as map data, not a verified route.
- OpenStreetMap data is fetched through Overpass QL with explicit bounding
  boxes and `out geom`. Open-Meteo supplies the seven-day hourly forecast,
  local sunrise/sunset values, and elevation samples. Packs preserve the
  required OpenStreetMap, Open-Meteo, and Copernicus DEM attribution.
- Context construction is filesystem-only and deterministic. User-reported rain
  overrides a dry forecast; user-reported fatigue and pace are preserved. A
  nearest forecast sample more than 90 minutes away is marked stale.
- Adaptation has no LLM dependency. At ten minutes of daylight or less it ends
  questing; under 45 minutes it limits duration and swaps movement/photo tasks;
  rain removes dry-ground, movement, and photo tasks; fatigue selects an easy
  stationary task; slow pace shortens movement. The existing safety guard gets
  the final decision and can force a swap or end.
- Lost/hurt keywords are evaluated before intent parsing. The deterministic
  response ends an active quest and says to stop, stay put somewhere safe away
  from edges/water, use the phone's emergency call, and that Wild Quest is not
  an emergency system.

Official sources checked before implementation: the [Overpass QL language
guide][overpass], [Open-Meteo forecast API][openmeteo-forecast], and
[Open-Meteo elevation API][openmeteo-elevation].

[overpass]: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
[openmeteo-forecast]: https://open-meteo.com/en/docs
[openmeteo-elevation]: https://open-meteo.com/en/docs/elevation-api

## 2026-10-07 — Phase 4 BirdNET route

- Hardware remains the Phase 0 target: Apple M2 with 8 GB unified memory.
- `birdnet==1.1.1` is pinned in `pyproject.toml` and all transitive packages are
  locked. The current official package supports LiteRT on macOS ARM64 with
  Python 3.11–3.13. We use the BirdNET 2.4 FP16 TFLite model through LiteRT,
  avoiding the full TensorFlow dependency and reducing the model from about
  52 MB FP32 to about 26 MB FP16.
- Model acquisition remains in `scripts/prefetch_models.py`. Runtime validates
  exact model size plus all 27 label files before importing BirdNET, sets
  `BIRDNET_APP_DATA` to `models/birdnet`, and fails with an offline instruction
  if assets are incomplete.
- A curated 24-species Maharashtra/India list uses exact BirdNET 2.4 labels.
  The default threshold is 0.25 and is configurable. At 0.10 the public test set
  recovered its weak Common Myna label but ranked Common Tailorbird above it;
  0.25 is the more conservative default.
- BirdNET detections are sensor evidence only. The service logs them to SQLite,
  moves `active → verifying`, and passes typed evidence to the existing Python
  state machine. BirdNET never writes state or awards XP.
- BirdNET source is MIT licensed. Its models are CC BY-NC-SA 4.0; commercial
  distribution or use requires a separate licensing review.

Official sources checked: the current [BirdNET Python package README][birdnet]
and [BirdNET-Analyzer installation guide][birdnet-install].

[birdnet]: https://github.com/birdnet-team/birdnet
[birdnet-install]: https://birdnet-team.github.io/BirdNET-Analyzer/stable/installation.html
