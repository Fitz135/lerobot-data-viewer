from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "datasets.yaml"
DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "viewer.sqlite"


@dataclass(frozen=True)
class DatasetConfig:
    id: str
    name: str
    root: Path


@dataclass(frozen=True)
class IndexConfig:
    parquet_workers: int = 4
    ffprobe_workers: int = 4
    duration_abs_tolerance_sec: float = 0.5
    duration_rel_tolerance: float = 0.02
    extreme_abs_value: float = 1_000_000.0


@dataclass(frozen=True)
class AppConfig:
    datasets: list[DatasetConfig]
    index: IndexConfig
    db_path: Path

    def dataset(self, dataset_id: str) -> DatasetConfig:
        for dataset in self.datasets:
            if dataset.id == dataset_id:
                return dataset
        raise KeyError(f"Unknown dataset id: {dataset_id}")


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or Path(os.environ.get("LDRV_CONFIG", DEFAULT_CONFIG_PATH))
    raw = yaml.safe_load(path.read_text()) or {}
    datasets = [
        DatasetConfig(
            id=str(item["id"]),
            name=str(item.get("name") or item["id"]),
            root=Path(item["root"]).expanduser().resolve(),
        )
        for item in raw.get("datasets", [])
    ]
    index_raw: dict[str, Any] = raw.get("index", {}) or {}
    index = IndexConfig(
        parquet_workers=int(index_raw.get("parquet_workers", 4)),
        ffprobe_workers=int(index_raw.get("ffprobe_workers", 4)),
        duration_abs_tolerance_sec=float(index_raw.get("duration_abs_tolerance_sec", 0.5)),
        duration_rel_tolerance=float(index_raw.get("duration_rel_tolerance", 0.02)),
        extreme_abs_value=float(index_raw.get("extreme_abs_value", 1_000_000.0)),
    )
    db_path = Path(os.environ.get("LDRV_DB_PATH", DEFAULT_DB_PATH)).expanduser().resolve()
    return AppConfig(datasets=datasets, index=index, db_path=db_path)


def ensure_path_in_dataset(dataset: DatasetConfig, path: str | Path) -> Path:
    root = dataset.root.resolve()
    candidate = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path is outside registered dataset root: {candidate}") from exc
    return candidate

