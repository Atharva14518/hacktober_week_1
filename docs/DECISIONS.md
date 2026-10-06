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
