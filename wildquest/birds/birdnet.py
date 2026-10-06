"""BirdNET 2.4 inference through lightweight LiteRT, with no runtime downloads."""

from __future__ import annotations

import importlib
import os
import time
from pathlib import Path
from typing import Protocol

import soundfile

from wildquest.birds.models import BirdAnalysis, BirdDetection


MODEL_SIZE = 25_932_528
MODEL_RELATIVE_PATH = Path("acoustic-models/v2.4/tf/model-fp16.tflite")
LABEL_RELATIVE_PATH = Path("acoustic-models/v2.4/tf/labels/en_us.txt")


class BirdClassifier(Protocol):
    def analyze(self, audio_path: Path) -> BirdAnalysis: ...


class BirdNetAssets:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @property
    def model_path(self) -> Path:
        return self.root / MODEL_RELATIVE_PATH

    @property
    def label_path(self) -> Path:
        return self.root / LABEL_RELATIVE_PATH

    def ready(self) -> bool:
        return (
            self.model_path.is_file()
            and self.model_path.stat().st_size == MODEL_SIZE
            and self.label_path.is_file()
            and len(list(self.label_path.parent.glob("*.txt"))) == 27
        )

    def require(self) -> None:
        if not self.ready():
            raise RuntimeError(
                "BirdNET assets are incomplete; run "
                "`uv run python scripts/prefetch_models.py --birdnet-only` online"
            )


class BirdNetLiteRT:
    """Reusable process-local BirdNET model filtered to a curated species set."""

    def __init__(
        self,
        *,
        assets: Path,
        species_list: Path,
        threshold: float = 0.4,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("confidence threshold must be between zero and one")
        self.assets = BirdNetAssets(assets)
        self.assets.require()
        self.species = _load_species(species_list)
        self.threshold = threshold
        os.environ["BIRDNET_APP_DATA"] = str(self.assets.root)
        birdnet = importlib.import_module("birdnet")
        local_data = importlib.import_module("birdnet.utils.local_data")
        if Path(local_data.APP_DIR).resolve() != self.assets.root:
            raise RuntimeError(
                "BirdNET was imported before BIRDNET_APP_DATA was configured"
            )
        self._model = birdnet.load(
            "acoustic", "2.4", "tf", precision="fp16", library="litert"
        )
        unavailable = set(self.species) - set(self._model.species_list)
        if unavailable:
            raise ValueError(
                "species list contains labels absent from BirdNET 2.4: "
                + ", ".join(sorted(unavailable))
            )

    def analyze(self, audio_path: Path) -> BirdAnalysis:
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        info = soundfile.info(str(audio_path))
        if not 0 < info.duration <= 60:
            raise ValueError("bird audio must be between 0 and 60 seconds")
        started = time.perf_counter()
        result = self._model.predict(
            audio_path,
            top_k=5,
            n_producers=1,
            n_workers=1,
            batch_size=1,
            custom_species_list=self.species,
            default_confidence_threshold=self.threshold,
        )
        inference_s = time.perf_counter() - started
        detections = tuple(
            sorted(
                (
                    _detection(str(row["species_name"]), row)
                    for row in result.to_structured_array()
                ),
                key=lambda item: (-item.confidence, item.start_s, item.label),
            )
        )
        return BirdAnalysis(
            audio_path=str(audio_path),
            audio_duration_s=float(info.duration),
            inference_s=inference_s,
            threshold=self.threshold,
            detections=detections,
        )


def _load_species(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise FileNotFoundError(path)
    species = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not species or len(species) != len(set(species)):
        raise ValueError("species list must be non-empty and contain unique labels")
    if any("_" not in label for label in species):
        raise ValueError("species labels must use BirdNET scientific_common format")
    return species


def _detection(label: str, row: object) -> BirdDetection:
    scientific_name, common_name = label.split("_", 1)
    return BirdDetection(
        label=label,
        scientific_name=scientific_name,
        common_name=common_name,
        confidence=float(row["confidence"]),  # type: ignore[index]
        start_s=float(row["start_time"]),  # type: ignore[index]
        end_s=float(row["end_time"]),  # type: ignore[index]
    )
