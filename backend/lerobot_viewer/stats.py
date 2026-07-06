from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class MatrixStats:
    names: list[str]
    min: list[float | None]
    max: list[float | None]
    mean: list[float | None]
    std: list[float | None]
    nan_count: int
    inf_count: int
    constant_dims: list[str]
    all_zero: bool
    extreme_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "names": self.names,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "std": self.std,
            "nan_count": self.nan_count,
            "inf_count": self.inf_count,
            "constant_dims": self.constant_dims,
            "all_zero": self.all_zero,
            "extreme_count": self.extreme_count,
        }


def percentile(values: list[int], pct: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), pct))


def compute_matrix_stats(
    rows: list[list[float]],
    names: list[str] | None,
    extreme_abs_value: float,
) -> MatrixStats:
    if not rows:
        resolved_names = names or []
        return MatrixStats(resolved_names, [], [], [], [], 0, 0, [], False, 0)
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.ndim == 1:
        matrix = matrix.reshape((-1, 1))
    width = int(matrix.shape[1])
    resolved_names = names or [f"dim_{idx}" for idx in range(width)]
    if len(resolved_names) != width:
        resolved_names = [f"dim_{idx}" for idx in range(width)]

    nan_mask = np.isnan(matrix)
    inf_mask = np.isinf(matrix)
    finite_mask = np.isfinite(matrix)
    safe = np.where(finite_mask, matrix, np.nan)

    def values_or_none(fn: Any) -> list[float | None]:
        result: list[float | None] = []
        for dim in range(width):
            column = safe[:, dim]
            if np.all(np.isnan(column)):
                result.append(None)
            else:
                result.append(float(fn(column)))
        return result

    mins = values_or_none(np.nanmin)
    maxs = values_or_none(np.nanmax)
    means = values_or_none(np.nanmean)
    stds = values_or_none(np.nanstd)
    constant_dims: list[str] = []
    for dim in range(width):
        finite_values = matrix[finite_mask[:, dim], dim]
        if finite_values.size > 0 and float(np.max(finite_values)) == float(np.min(finite_values)):
            constant_dims.append(resolved_names[dim])

    finite_values = matrix[finite_mask]
    all_zero = bool(finite_values.size > 0 and np.all(finite_values == 0))
    extreme_count = int(np.sum(np.abs(finite_values) > extreme_abs_value))
    return MatrixStats(
        names=resolved_names,
        min=mins,
        max=maxs,
        mean=means,
        std=stds,
        nan_count=int(np.sum(nan_mask)),
        inf_count=int(np.sum(inf_mask)),
        constant_dims=constant_dims,
        all_zero=all_zero,
        extreme_count=extreme_count,
    )


def aggregate_stats(stats_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not stats_items:
        return {}
    names = stats_items[0].get("names", [])
    width = len(names)
    mins: list[float | None] = []
    maxs: list[float | None] = []
    means: list[float | None] = []
    stds: list[float | None] = []
    for dim in range(width):
        dim_mins = [item["min"][dim] for item in stats_items if item.get("min") and item["min"][dim] is not None]
        dim_maxs = [item["max"][dim] for item in stats_items if item.get("max") and item["max"][dim] is not None]
        dim_means = [item["mean"][dim] for item in stats_items if item.get("mean") and item["mean"][dim] is not None]
        dim_stds = [item["std"][dim] for item in stats_items if item.get("std") and item["std"][dim] is not None]
        mins.append(float(min(dim_mins)) if dim_mins else None)
        maxs.append(float(max(dim_maxs)) if dim_maxs else None)
        means.append(float(np.mean(dim_means)) if dim_means else None)
        stds.append(float(np.mean(dim_stds)) if dim_stds else None)
    constant_sets = [set(item.get("constant_dims", [])) for item in stats_items]
    constant_dims = sorted(set.intersection(*constant_sets)) if constant_sets else []
    return {
        "names": names,
        "min": mins,
        "max": maxs,
        "mean": means,
        "std": stds,
        "nan_count": int(sum(item.get("nan_count", 0) for item in stats_items)),
        "inf_count": int(sum(item.get("inf_count", 0) for item in stats_items)),
        "constant_dims": constant_dims,
        "all_zero": bool(stats_items and all(item.get("all_zero", False) for item in stats_items)),
        "extreme_count": int(sum(item.get("extreme_count", 0) for item in stats_items)),
    }

