.PHONY: setup test run bench prefetch quest-smoke

PYTHON := uv run --locked python

setup:
	uv sync --locked
	$(PYTHON) scripts/verify_setup.py

prefetch:
	$(PYTHON) scripts/prefetch_models.py

test:
	uv run --locked pytest

run:
	$(PYTHON) scripts/smoke_test.py

quest-smoke:
	$(PYTHON) scripts/quest_smoke.py

bench:
	$(PYTHON) scripts/bench_stt.py
	$(PYTHON) scripts/smoke_test.py --audio vendor/whisper.cpp/samples/jfk.wav --no-play
	$(PYTHON) scripts/bench_tts.py
