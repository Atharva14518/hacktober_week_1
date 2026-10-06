# Phase 0 report — 2026-10-07

## What works

- Native arm64 uv environment on an 8 GB Apple M2 MacBook Air.
- Ollama 0.40.0 with Qwen 2.5 3B Instruct and Gemma 3 4B Q4 models.
- whisper.cpp v1.9.4 built with Accelerate and Metal; base and small models.
- Piper 1.8.0 voice output, plus a working Kokoro ONNX 0.6.1 FP16 comparison.
- Five-second microphone → Whisper → Ollama → Piper → `afplay` loop.
- Stage timings printed and persisted to SQLite. Runtime uses loopback only.
- Acceptance run completed while `networksetup` reported Wi-Fi Off; Wi-Fi was
  restored after the run.

## Measured latency

Final Wi-Fi-off microphone acceptance run (ambient silence triggered the
documented safe fallback prompt): microphone command 5.891 s including
AVFoundation startup and 5.000 s capture; STT 0.639 s; Qwen first token 3.882 s;
Qwen total 4.305 s; Piper TTS 1.083 s; turn total 11.917 s. The row was written
to `data/wildquest.db`. A separate acoustic-loop run confirmed non-silent mic
audio was transcribed and sent through the full pipeline (2.848 s after warm-up),
though speaker-to-microphone distortion made its transcript unsuitable as an
accuracy measurement.

On the 11-second bundled JFK sample after warm-up, Whisper base took 0.796 s and
small took 2.251 s; both produced the expected sentence, with only punctuation
differing. Cold Qwen full turn: 32.848 s (STT shader/model cold start 24.878 s,
first token 6.359 s). Cold Gemma full turn after model swap: 72.430 s (first token
41.133 s). Same-sentence TTS: Piper 2.108 s cold; Kokoro 2.767 s cold.

## Recommendation and known issues

Use Qwen 2.5 3B Q4_K_M, Whisper base, and Piper. Gemma's 3.3 GB image creates
severe model-swap pressure on 8 GB RAM. Whisper small is roughly 2.8× slower on
the test sample without a material accuracy gain. First-ever Whisper inference
has a Metal shader/model warm-up cost. AVFoundation added about 4.3 s of startup
overhead to the nominal five-second capture. Kokoro works and may sound more
natural, but is slower here and emits harmless ONNX constant-folding warnings.
The automated acceptance recording contained no speaker input, so the tested
safe fallback supplied the LLM prompt; the entire offline audio pipeline still
completed and played the reply.
