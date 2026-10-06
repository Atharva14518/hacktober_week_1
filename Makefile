.PHONY: setup test run bench prefetch prefetch-location quest-smoke place-demo \
	bird-prefetch bird-testset bird-bench bird-run

PYTHON := uv run --locked python

setup:
	uv sync --locked
	$(PYTHON) scripts/verify_setup.py

prefetch:
	$(PYTHON) scripts/prefetch_models.py

TRAIL ?= sinhagad

prefetch-location:
	$(PYTHON) scripts/prefetch_location.py $(TRAIL)

bird-prefetch:
	$(PYTHON) scripts/prefetch_models.py --birdnet-only

bird-testset:
	$(PYTHON) scripts/prefetch_bird_samples.py

test:
	uv run --locked pytest

run:
	$(PYTHON) scripts/smoke_test.py

quest-smoke:
	$(PYTHON) scripts/quest_smoke.py

place-demo:
	$(PYTHON) scripts/place_demo.py $(TRAIL)

bird-bench:
	$(PYTHON) scripts/bench_birds.py

bird-run:
	$(PYTHON) scripts/bird_quest.py --trail $(TRAIL)

bench:
	$(PYTHON) scripts/bench_stt.py
	$(PYTHON) scripts/smoke_test.py --audio vendor/whisper.cpp/samples/jfk.wav --no-play
	$(PYTHON) scripts/bench_tts.py
