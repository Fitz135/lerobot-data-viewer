from __future__ import annotations

import json
import math
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .config import AppConfig, DatasetConfig, ensure_path_in_dataset
from .db import connect, init_db, insert_registered_datasets, json_dump
from .stats import aggregate_stats, compute_matrix_stats, percentile


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def health(
    severity: str,
    code: str,
    message: str,
    path: Path | str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "path": str(path) if path else None,
        "details": details or {},
    }


def severity_counts(checks: list[dict[str, Any]]) -> tuple[int, int, int]:
    errors = sum(1 for item in checks if item["severity"] == "error")
    warnings = sum(1 for item in checks if item["severity"] == "warning")
    infos = sum(1 for item in checks if item["severity"] == "info")
    return errors, warnings, infos


def video_keys(info: dict[str, Any]) -> list[str]:
    features = info.get("features", {})
    return sorted(
        key
        for key, value in features.items()
        if isinstance(value, dict) and value.get("dtype") == "video"
    )


def feature_names(info: dict[str, Any], key: str) -> list[str]:
    feature = info.get("features", {}).get(key, {}) or {}
    names = feature.get("names")
    if isinstance(names, list):
        return [str(item) for item in names]
    shape = feature.get("shape") or []
    if shape:
        return [f"dim_{idx}" for idx in range(int(shape[0]))]
    return []


def schema_summary(info: dict[str, Any]) -> dict[str, Any]:
    features = info.get("features", {})
    return {
        "robot_type": info.get("robot_type"),
        "fps": info.get("fps"),
        "state": features.get("observation.state"),
        "action": features.get("action"),
        "videos": {key: features[key] for key in video_keys(info)},
    }


def format_lerobot_path(pattern: str, episode_index: int, chunks_size: int, video_key: str | None = None) -> str:
    episode_chunk = int(episode_index) // int(chunks_size or 1000)
    values: dict[str, Any] = {
        "episode_chunk": episode_chunk,
        "episode_index": int(episode_index),
    }
    if video_key is not None:
        values["video_key"] = video_key
    return pattern.format(**values)


def parse_fraction(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num_text, denom_text = value.split("/", 1)
        denom = float(denom_text)
        if denom == 0:
            return None
        return float(num_text) / denom
    return float(value)


def probe_video(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffprobe exited {result.returncode}")
    raw = json.loads(result.stdout or "{}")
    stream = (raw.get("streams") or [{}])[0]
    duration = stream.get("duration") or (raw.get("format") or {}).get("duration")
    fps = parse_fraction(stream.get("avg_frame_rate")) or parse_fraction(stream.get("r_frame_rate"))
    nb_frames = stream.get("nb_frames")
    return {
        "codec": stream.get("codec_name"),
        "width": int(stream["width"]) if stream.get("width") is not None else None,
        "height": int(stream["height"]) if stream.get("height") is not None else None,
        "fps": float(fps) if fps is not None else None,
        "duration_sec": float(duration) if duration is not None else None,
        "nb_frames": int(nb_frames) if nb_frames not in (None, "N/A") else None,
    }


def column_pylist(table: Any, name: str) -> list[Any]:
    if name not in table.column_names:
        return []
    return table.column(name).to_pylist()


def read_parquet_summary(
    path: Path,
    state_names: list[str],
    action_names: list[str],
    extreme_abs_value: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    pf = pq.ParquetFile(path)
    row_count = int(pf.metadata.num_rows)
    columns = set(pf.schema_arrow.names)
    required = ["observation.state", "action", "frame_index", "timestamp"]
    missing = [name for name in required if name not in columns]
    if missing:
        checks.append(
            health(
                "error",
                "missing_parquet_columns",
                f"Parquet is missing required columns: {', '.join(missing)}",
                path,
                {"missing": missing},
            )
        )
        return {
            "row_count": row_count,
            "frame_start": None,
            "frame_end": None,
            "timestamp_start": None,
            "timestamp_end": None,
            "state_stats": {},
            "action_stats": {},
        }, checks

    table = pq.read_table(path, columns=required)
    frame_values = [int(item) for item in column_pylist(table, "frame_index")]
    timestamp_values = [float(item) for item in column_pylist(table, "timestamp")]
    state_rows = column_pylist(table, "observation.state")
    action_rows = column_pylist(table, "action")
    state_stats = compute_matrix_stats(state_rows, state_names, extreme_abs_value).to_dict()
    action_stats = compute_matrix_stats(action_rows, action_names, extreme_abs_value).to_dict()

    for label, stats in (("observation.state", state_stats), ("action", action_stats)):
        if stats.get("nan_count", 0) or stats.get("inf_count", 0):
            checks.append(
                health(
                    "error",
                    "nan_or_inf",
                    f"{label} contains NaN or Inf values",
                    path,
                    {"nan_count": stats.get("nan_count", 0), "inf_count": stats.get("inf_count", 0)},
                )
            )
        if stats.get("all_zero"):
            checks.append(
                health(
                    "warning",
                    "all_zero",
                    f"{label} is all zero for this episode",
                    path,
                    {},
                )
            )
        names = stats.get("names") or []
        constant_dims = stats.get("constant_dims") or []
        if names and len(constant_dims) == len(names):
            checks.append(
                health(
                    "warning",
                    "all_dimensions_constant",
                    f"{label} is constant in all dimensions",
                    path,
                    {"dimension_count": len(names)},
                )
            )
        elif constant_dims:
            checks.append(
                health(
                    "info",
                    "constant_dimensions",
                    f"{label} has {len(constant_dims)} constant dimensions",
                    path,
                    {"constant_dims": constant_dims[:20], "total": len(constant_dims)},
                )
            )
        if stats.get("extreme_count", 0):
            checks.append(
                health(
                    "warning",
                    "extreme_values",
                    f"{label} contains very large absolute values",
                    path,
                    {"extreme_count": stats.get("extreme_count", 0)},
                )
            )

    return {
        "row_count": row_count,
        "frame_start": min(frame_values) if frame_values else None,
        "frame_end": max(frame_values) if frame_values else None,
        "timestamp_start": min(timestamp_values) if timestamp_values else None,
        "timestamp_end": max(timestamp_values) if timestamp_values else None,
        "state_stats": state_stats,
        "action_stats": action_stats,
    }, checks


@dataclass(frozen=True)
class EpisodeJob:
    dataset: DatasetConfig
    task_id: str
    task_root: Path
    info: dict[str, Any]
    episode: dict[str, Any]
    task_text: str | None
    camera_keys: list[str]
    state_names: list[str]
    action_names: list[str]
    index_config: Any


@dataclass
class EpisodeResult:
    episode: dict[str, Any]
    videos: list[dict[str, Any]]
    checks: list[dict[str, Any]]


def scan_episode(job: EpisodeJob) -> EpisodeResult:
    info = job.info
    episode_index = int(job.episode["episode_index"])
    length = int(job.episode["length"])
    fps = float(info.get("fps") or 0)
    duration_sec = float(length / fps) if fps else 0.0
    chunks_size = int(info.get("chunks_size") or 1000)
    data_path = format_lerobot_path(info["data_path"], episode_index, chunks_size)
    parquet_path = ensure_path_in_dataset(job.dataset, job.task_root / data_path)
    checks: list[dict[str, Any]] = []
    parquet_summary: dict[str, Any] = {
        "row_count": None,
        "frame_start": None,
        "frame_end": None,
        "timestamp_start": None,
        "timestamp_end": None,
        "state_stats": {},
        "action_stats": {},
    }
    if not parquet_path.exists():
        checks.append(health("error", "missing_parquet", "Episode parquet file is missing", parquet_path))
    else:
        try:
            parquet_summary, parquet_checks = read_parquet_summary(
                parquet_path,
                job.state_names,
                job.action_names,
                job.index_config.extreme_abs_value,
            )
            checks.extend(parquet_checks)
        except Exception as exc:  # noqa: BLE001
            checks.append(
                health(
                    "error",
                    "parquet_read_failed",
                    f"Failed to read parquet: {exc}",
                    parquet_path,
                    {"traceback": traceback.format_exc(limit=2)},
                )
            )
    if parquet_summary.get("row_count") is not None and int(parquet_summary["row_count"]) != length:
        checks.append(
            health(
                "error",
                "parquet_row_count_mismatch",
                "Parquet row count does not match episodes.jsonl length",
                parquet_path,
                {"row_count": parquet_summary["row_count"], "episode_length": length},
            )
        )

    video_rows: list[dict[str, Any]] = []
    for camera_key in job.camera_keys:
        relative = format_lerobot_path(info["video_path"], episode_index, chunks_size, camera_key)
        video_path = ensure_path_in_dataset(job.dataset, job.task_root / relative)
        video_row: dict[str, Any] = {
            "camera_key": camera_key,
            "path": str(video_path),
            "exists_flag": int(video_path.exists()),
            "width": None,
            "height": None,
            "fps": None,
            "duration_sec": None,
            "codec": None,
            "nb_frames": None,
            "probe_error": None,
        }
        if not video_path.exists():
            checks.append(health("error", "missing_video", f"Missing video for {camera_key}", video_path))
            video_rows.append(video_row)
            continue
        try:
            probe = probe_video(video_path)
            video_row.update(probe)
            feature = info.get("features", {}).get(camera_key, {}) or {}
            expected_info = feature.get("info", {}) or {}
            expected_width = expected_info.get("video.width")
            expected_height = expected_info.get("video.height")
            expected_fps = expected_info.get("video.fps") or fps
            if expected_width and probe.get("width") and int(expected_width) != int(probe["width"]):
                checks.append(
                    health(
                        "warning",
                        "video_width_mismatch",
                        f"{camera_key} width differs from info.json",
                        video_path,
                        {"expected": expected_width, "actual": probe["width"]},
                    )
                )
            if expected_height and probe.get("height") and int(expected_height) != int(probe["height"]):
                checks.append(
                    health(
                        "warning",
                        "video_height_mismatch",
                        f"{camera_key} height differs from info.json",
                        video_path,
                        {"expected": expected_height, "actual": probe["height"]},
                    )
                )
            if expected_fps and probe.get("fps") and abs(float(expected_fps) - float(probe["fps"])) > 0.1:
                checks.append(
                    health(
                        "warning",
                        "video_fps_mismatch",
                        f"{camera_key} fps differs from info.json",
                        video_path,
                        {"expected": expected_fps, "actual": probe["fps"]},
                    )
                )
            actual_duration = probe.get("duration_sec")
            if actual_duration is not None and duration_sec:
                diff = abs(float(actual_duration) - duration_sec)
                rel = diff / duration_sec if duration_sec else math.inf
                if diff > job.index_config.duration_abs_tolerance_sec and rel > job.index_config.duration_rel_tolerance:
                    checks.append(
                        health(
                            "warning",
                            "video_duration_mismatch",
                            f"{camera_key} duration differs from episode length/fps",
                            video_path,
                            {"expected": duration_sec, "actual": actual_duration, "abs_diff": diff, "rel_diff": rel},
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            video_row["probe_error"] = str(exc)
            checks.append(
                health(
                    "error",
                    "video_probe_failed",
                    f"ffprobe failed for {camera_key}: {exc}",
                    video_path,
                )
            )
        video_rows.append(video_row)

    errors, warnings, infos = severity_counts(checks)
    episode_row = {
        "task_id": job.task_id,
        "episode_index": episode_index,
        "length": length,
        "fps": fps,
        "duration_sec": duration_sec,
        "parquet_path": str(parquet_path),
        "task_text": job.task_text,
        "cameras": job.camera_keys,
        "frame_start": parquet_summary.get("frame_start"),
        "frame_end": parquet_summary.get("frame_end"),
        "timestamp_start": parquet_summary.get("timestamp_start"),
        "timestamp_end": parquet_summary.get("timestamp_end"),
        "row_count": parquet_summary.get("row_count"),
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "state_stats": parquet_summary.get("state_stats") or {},
        "action_stats": parquet_summary.get("action_stats") or {},
    }
    return EpisodeResult(episode=episode_row, videos=video_rows, checks=checks)


def insert_run_event(conn: Any, run_id: int, level: str, message: str, path: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO index_events(run_id, level, message, path, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, level, message, path, now_iso()),
    )


def update_run(
    conn: Any,
    run_id: int,
    *,
    status: str | None = None,
    phase: str | None = None,
    processed_items: int | None = None,
    total_items: int | None = None,
    error_message: str | None = None,
    finished: bool = False,
) -> None:
    current = conn.execute("SELECT * FROM index_runs WHERE id = ?", (run_id,)).fetchone()
    conn.execute(
        """
        UPDATE index_runs
        SET status = ?, phase = ?, processed_items = ?, total_items = ?,
            error_message = COALESCE(?, error_message),
            finished_at = CASE WHEN ? THEN ? ELSE finished_at END
        WHERE id = ?
        """,
        (
            status or current["status"],
            phase or current["phase"],
            processed_items if processed_items is not None else current["processed_items"],
            total_items if total_items is not None else current["total_items"],
            error_message,
            1 if finished else 0,
            now_iso(),
            run_id,
        ),
    )
    conn.commit()


def create_generation_and_run(conn: Any, dataset_id: str, is_smoke: bool) -> tuple[int, int]:
    created_at = now_iso()
    cur = conn.execute(
        "INSERT INTO generations(dataset_id, created_at, is_smoke) VALUES (?, ?, ?)",
        (dataset_id, created_at, 1 if is_smoke else 0),
    )
    generation_id = int(cur.lastrowid)
    cur = conn.execute(
        """
        INSERT INTO index_runs(dataset_id, generation_id, status, phase, started_at)
        VALUES (?, ?, 'running', 'metadata', ?)
        """,
        (dataset_id, generation_id, created_at),
    )
    run_id = int(cur.lastrowid)
    conn.commit()
    return generation_id, run_id


def read_task_metadata(task_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[int, str]]:
    info = load_json(task_root / "meta" / "info.json")
    episodes = load_jsonl(task_root / "meta" / "episodes.jsonl")
    task_map: dict[int, str] = {}
    tasks_path = task_root / "meta" / "tasks.jsonl"
    if tasks_path.exists():
        for item in load_jsonl(tasks_path):
            task_map[int(item["task_index"])] = str(item["task"])
    return info, episodes, task_map


def task_text_for_episode(episode: dict[str, Any], task_map: dict[int, str]) -> str | None:
    task_index = episode.get("task_index")
    if task_index is not None and int(task_index) in task_map:
        return task_map[int(task_index)]
    tasks = episode.get("tasks")
    if isinstance(tasks, list) and tasks:
        return str(tasks[0])
    return next(iter(task_map.values()), None)


def write_scan_results(
    conn: Any,
    dataset: DatasetConfig,
    generation_id: int,
    task_infos: dict[str, dict[str, Any]],
    results: list[EpisodeResult],
) -> None:
    task_groups: dict[str, list[EpisodeResult]] = {}
    for result in results:
        task_groups.setdefault(result.episode["task_id"], []).append(result)

    for result in results:
        ep = result.episode
        conn.execute(
            """
            INSERT INTO episodes(
                dataset_id, generation_id, task_id, episode_index, length, fps, duration_sec,
                parquet_path, task_text, cameras_json, frame_start, frame_end,
                timestamp_start, timestamp_end, row_count, error_count, warning_count,
                info_count, state_stats_json, action_stats_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset.id,
                generation_id,
                ep["task_id"],
                ep["episode_index"],
                ep["length"],
                ep["fps"],
                ep["duration_sec"],
                ep["parquet_path"],
                ep["task_text"],
                json_dump(ep["cameras"]),
                ep["frame_start"],
                ep["frame_end"],
                ep["timestamp_start"],
                ep["timestamp_end"],
                ep["row_count"],
                ep["error_count"],
                ep["warning_count"],
                ep["info_count"],
                json_dump(ep["state_stats"]),
                json_dump(ep["action_stats"]),
            ),
        )
        for video in result.videos:
            conn.execute(
                """
                INSERT INTO episode_videos(
                    dataset_id, generation_id, task_id, episode_index, camera_key, path,
                    exists_flag, width, height, fps, duration_sec, codec, nb_frames, probe_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset.id,
                    generation_id,
                    ep["task_id"],
                    ep["episode_index"],
                    video["camera_key"],
                    video["path"],
                    video["exists_flag"],
                    video["width"],
                    video["height"],
                    video["fps"],
                    video["duration_sec"],
                    video["codec"],
                    video["nb_frames"],
                    video["probe_error"],
                ),
            )
        for check in result.checks:
            conn.execute(
                """
                INSERT INTO health_checks(
                    dataset_id, generation_id, task_id, episode_index, severity,
                    code, message, path, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset.id,
                    generation_id,
                    ep["task_id"],
                    ep["episode_index"],
                    check["severity"],
                    check["code"],
                    check["message"],
                    check["path"],
                    json_dump(check["details"]),
                ),
            )

    task_rows: list[dict[str, Any]] = []
    for task_id, group in sorted(task_groups.items()):
        lengths = [item.episode["length"] for item in group]
        state_stats = aggregate_stats([item.episode["state_stats"] for item in group if item.episode["state_stats"]])
        action_stats = aggregate_stats([item.episode["action_stats"] for item in group if item.episode["action_stats"]])
        errors = sum(item.episode["error_count"] for item in group)
        warnings = sum(item.episode["warning_count"] for item in group)
        infos = sum(item.episode["info_count"] for item in group)
        video_count = sum(len(item.videos) for item in group)
        duration = sum(float(item.episode["duration_sec"]) for item in group)
        first_ep = group[0].episode
        task_info = task_infos[task_id]
        task_row = {
            "task_id": task_id,
            "task_text": first_ep["task_text"],
            "episode_count": len(group),
            "frame_count": sum(lengths),
            "video_count": video_count,
            "duration_sec": duration,
            "min_length": min(lengths) if lengths else None,
            "p50_length": percentile(lengths, 50),
            "p95_length": percentile(lengths, 95),
            "max_length": max(lengths) if lengths else None,
            "error_count": errors,
            "warning_count": warnings,
            "info_count": infos,
            "cameras": video_keys(task_info),
            "schema": schema_summary(task_info),
            "state_stats": state_stats,
            "action_stats": action_stats,
        }
        task_rows.append(task_row)
        conn.execute(
            """
            INSERT INTO tasks(
                dataset_id, generation_id, task_id, task_text, episode_count,
                frame_count, video_count, duration_sec, min_length, p50_length,
                p95_length, max_length, error_count, warning_count, info_count,
                cameras_json, schema_json, state_stats_json, action_stats_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset.id,
                generation_id,
                task_id,
                task_row["task_text"],
                task_row["episode_count"],
                task_row["frame_count"],
                task_row["video_count"],
                task_row["duration_sec"],
                task_row["min_length"],
                task_row["p50_length"],
                task_row["p95_length"],
                task_row["max_length"],
                task_row["error_count"],
                task_row["warning_count"],
                task_row["info_count"],
                json_dump(task_row["cameras"]),
                json_dump(task_row["schema"]),
                json_dump(task_row["state_stats"]),
                json_dump(task_row["action_stats"]),
            ),
        )

    dataset_state_stats = aggregate_stats([row["state_stats"] for row in task_rows if row["state_stats"]])
    dataset_action_stats = aggregate_stats([row["action_stats"] for row in task_rows if row["action_stats"]])
    all_cameras = sorted({camera for row in task_rows for camera in row["cameras"]})
    first_schema = task_rows[0]["schema"] if task_rows else {}
    conn.execute(
        """
        INSERT INTO dataset_stats(
            dataset_id, generation_id, task_count, episode_count, frame_count,
            video_count, duration_sec, error_count, warning_count, info_count,
            cameras_json, schema_json, state_stats_json, action_stats_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset.id,
            generation_id,
            len(task_rows),
            sum(row["episode_count"] for row in task_rows),
            sum(row["frame_count"] for row in task_rows),
            sum(row["video_count"] for row in task_rows),
            sum(row["duration_sec"] for row in task_rows),
            sum(row["error_count"] for row in task_rows),
            sum(row["warning_count"] for row in task_rows),
            sum(row["info_count"] for row in task_rows),
            json_dump(all_cameras),
            json_dump(first_schema),
            json_dump(dataset_state_stats),
            json_dump(dataset_action_stats),
            now_iso(),
        ),
    )
    conn.commit()


def index_dataset(
    app_config: AppConfig,
    dataset_id: str,
    *,
    smoke: bool = False,
    max_tasks: int | None = None,
    max_episodes_per_task: int | None = None,
) -> int:
    dataset = app_config.dataset(dataset_id)
    conn = connect(app_config.db_path)
    init_db(conn)
    insert_registered_datasets(conn, [(item.id, item.name, str(item.root)) for item in app_config.datasets])
    generation_id, run_id = create_generation_and_run(conn, dataset.id, smoke)
    insert_run_event(conn, run_id, "info", "Started indexing", str(dataset.root))
    try:
        if not dataset.root.exists():
            raise FileNotFoundError(f"Dataset root does not exist: {dataset.root}")

        task_dirs = sorted(
            path for path in dataset.root.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        )
        if max_tasks is not None:
            task_dirs = task_dirs[:max_tasks]
        update_run(conn, run_id, phase="metadata", total_items=len(task_dirs), processed_items=0)

        jobs: list[EpisodeJob] = []
        task_infos: dict[str, dict[str, Any]] = {}
        for processed, task_root in enumerate(task_dirs, start=1):
            try:
                info, episodes, task_map = read_task_metadata(task_root)
                task_infos[task_root.name] = info
                if max_episodes_per_task is not None:
                    episodes = episodes[:max_episodes_per_task]
                cameras = video_keys(info)
                for episode in episodes:
                    jobs.append(
                        EpisodeJob(
                            dataset=dataset,
                            task_id=task_root.name,
                            task_root=task_root,
                            info=info,
                            episode=episode,
                            task_text=task_text_for_episode(episode, task_map),
                            camera_keys=cameras,
                            state_names=feature_names(info, "observation.state"),
                            action_names=feature_names(info, "action"),
                            index_config=app_config.index,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                conn.execute(
                    """
                    INSERT INTO health_checks(
                        dataset_id, generation_id, task_id, episode_index, severity,
                        code, message, path, details_json
                    )
                    VALUES (?, ?, ?, NULL, 'error', 'metadata_read_failed', ?, ?, ?)
                    """,
                    (
                        dataset.id,
                        generation_id,
                        task_root.name,
                        f"Failed to read task metadata: {exc}",
                        str(task_root),
                        json_dump({"traceback": traceback.format_exc(limit=2)}),
                    ),
                )
                insert_run_event(conn, run_id, "error", f"Failed metadata for {task_root.name}: {exc}", str(task_root))
            update_run(conn, run_id, processed_items=processed, total_items=len(task_dirs))

        update_run(conn, run_id, phase="episodes", processed_items=0, total_items=len(jobs))
        results: list[EpisodeResult] = []
        worker_count = max(1, int(app_config.index.parquet_workers) + int(app_config.index.ffprobe_workers))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(scan_episode, job) for job in jobs]
            for processed, future in enumerate(as_completed(futures), start=1):
                results.append(future.result())
                if processed == len(futures) or processed % 10 == 0:
                    update_run(conn, run_id, processed_items=processed, total_items=len(futures))

        update_run(conn, run_id, phase="write_cache")
        write_scan_results(conn, dataset, generation_id, task_infos, results)
        conn.execute(
            """
            UPDATE datasets
            SET active_generation_id = ?, last_indexed_at = ?
            WHERE id = ?
            """,
            (generation_id, now_iso(), dataset.id),
        )
        insert_run_event(conn, run_id, "info", "Activated new generation")
        conn.commit()
        update_run(conn, run_id, status="success", phase="complete", finished=True)
        return run_id
    except Exception as exc:
        insert_run_event(conn, run_id, "error", f"Indexing failed: {exc}", str(dataset.root))
        update_run(
            conn,
            run_id,
            status="failed",
            phase="failed",
            error_message=str(exc),
            finished=True,
        )
        raise
    finally:
        conn.close()

