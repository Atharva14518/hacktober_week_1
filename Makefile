.PHONY: setup test run bench prefetch prefetch-location quest-smoke place-demo \
	bird-prefetch bird-testset bird-bench bird-run vision-prefetch vision-testset \
	vision-bench vision-run photo-server

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

vision-prefetch:
	$(PYTHON) scripts/prefetch_models.py --vision-only

vision-testset:
	$(PYTHON) scripts/prefetch_vision_samples.py

VISION_MODEL ?= qwen2.5vl:3b

vision-bench:
	$(PYTHON) scripts/bench_vision.py --model $(VISION_MODEL)

vision-run:
	$(PYTHON) scripts/vision_quest.py --trail $(TRAIL)

photo-server:
	$(PYTHON) scripts/photo_upload_server.py

bench:
	$(PYTHON) scripts/bench_stt.py
	$(PYTHON) scripts/smoke_test.py --audio vendor/whisper.cpp/samples/jfk.wav --no-play
	$(PYTHON) scripts/bench_tts.py
