from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def _as_scalar_list(values: list[Any], cast: Any) -> list[Any]:
    return [cast(item) for item in values]


def _downsample_indices(length: int, target: int | None) -> list[int]:
    if target is None or target <= 0 or length <= target:
        return list(range(length))
    if target == 1:
        return [0]
    step = (length - 1) / (target - 1)
    return [round(idx * step) for idx in range(target)]


def _series_from_matrix(
    rows: list[list[float]],
    names: list[str],
    prefix: str,
    indices: list[int],
) -> dict[str, list[float]]:
    if not rows:
        return {}
    width = len(rows[0])
    resolved_names = names if len(names) == width else [f"dim_{idx}" for idx in range(width)]
    result: dict[str, list[float]] = {}
    for dim, name in enumerate(resolved_names):
        result[f"{prefix}.{name}"] = [float(rows[row_idx][dim]) for row_idx in indices]
    return result


def _series_from_feature_columns(
    table: Any,
    specs: list[tuple[str, list[str]]],
    indices: list[int],
) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for key, names in specs:
        rows = table.column(key).to_pylist()
        if not rows:
            continue
        first = rows[0]
        width = len(first) if isinstance(first, list) else 1
        resolved_names = names if len(names) == width else [f"dim_{idx}" for idx in range(width)]
        for dim, name in enumerate(resolved_names):
            values: list[float] = []
            for row_idx in indices:
                value = rows[row_idx]
                values.append(float(value[dim] if isinstance(value, list) else value))
            result[f"{key}.{name}"] = values
    return result


def read_episode_timeseries(
    parquet_path: Path,
    state_specs: list[tuple[str, list[str]]],
    action_specs: list[tuple[str, list[str]]],
    downsample: int | None = None,
) -> dict[str, Any]:
    columns = list(dict.fromkeys(
        ["frame_index", "timestamp"]
        + [key for key, _ in state_specs]
        + [key for key, _ in action_specs]
    ))
    table = pq.read_table(parquet_path, columns=columns)
    frame_index = _as_scalar_list(table.column("frame_index").to_pylist(), int)
    timestamp = _as_scalar_list(table.column("timestamp").to_pylist(), float)
    indices = _downsample_indices(len(frame_index), downsample)
    series: dict[str, list[float]] = {}
    series.update(_series_from_feature_columns(table, state_specs, indices))
    series.update(_series_from_feature_columns(table, action_specs, indices))
    return {
        "frame_index": [frame_index[idx] for idx in indices],
        "timestamp": [timestamp[idx] for idx in indices],
        "series": series,
        "downsampled": len(indices) != len(frame_index),
        "source_length": len(frame_index),
    }

