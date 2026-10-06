# Phase 2 report — 2026-10-07

## What works

- Thirty hand-authored, strictly validated YAML quests cover observe, listen,
  find, move, silence, bird, and photo types with explicit safety constraints.
- The complete idle/offered/active/verifying/completed/skipped/ended state
  machine persists transactionally to SQLite and resumes after reconstruction.
- Easy/moderate/challenging XP, capped streak bonuses, and skip/end streak reset.
- Three narrator personas: epic fantasy, calm naturalist, and a lightly
  Hinglish/Marathi-flavoured local guide. Narration is limited to two through
  four spoken sentences and cannot mutate game state.
- Strict Pydantic JSON intent parsing for done, skip, hint, repeat, tired, stop,
  and unknown, with one retry and deterministic English/Hinglish/Marathi keyword
  fallback. Invalid JSON and extra fields fail safely.
- Code-level safety rejects unsafe contexts and overrides unsafe narration.
- A model-produced `done` reaches verifying with zero XP. Only typed verifier
  evidence can complete the quest.

## Tests and latency

The automated suite covers catalog validation, every quest type, safety gates,
state transitions, XP/streak, crash resume, scripted conversations, invalid JSON,
keyword fallback, narration bounds, and the completion-authority boundary.

The local-Qwen scripted smoke test produced a four-sentence local-guide quest,
then parsed “I found all three colors. I am done.” as `done`. Final state was
`verifying`, XP was zero, and both calls were logged to SQLite. Cold narrator:
9.532 s first token and 11.042 s total. Warm intent parser: 0.359 s first token
and 0.613 s total.

## Known issues

- The first narration after loading Qwen has a noticeable cold-start delay on
  this 8 GB M2. Keeping Qwen resident reduces subsequent intent latency.
- `user_confirmation` is an allowed deterministic verifier source for sensory
  quests; timer, sensor, and photo-metadata producers are interfaces for later
  device-integration work. They are deliberately outside the LLM adapter.
- Quest selection is deterministic catalog order in this phase; location-aware
  ranking can be added without changing completion authority or persistence.
