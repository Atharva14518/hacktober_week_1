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
