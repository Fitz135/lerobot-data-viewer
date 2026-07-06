from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            root TEXT NOT NULL,
            active_generation_id INTEGER,
            last_indexed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_smoke INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            generation_id INTEGER,
            status TEXT NOT NULL,
            phase TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            total_items INTEGER NOT NULL DEFAULT 0,
            processed_items INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS index_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            path TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dataset_stats (
            dataset_id TEXT NOT NULL,
            generation_id INTEGER NOT NULL,
            task_count INTEGER NOT NULL,
            episode_count INTEGER NOT NULL,
            frame_count INTEGER NOT NULL,
            video_count INTEGER NOT NULL,
            duration_sec REAL NOT NULL,
            error_count INTEGER NOT NULL,
            warning_count INTEGER NOT NULL,
            info_count INTEGER NOT NULL,
            cameras_json TEXT NOT NULL,
            schema_json TEXT NOT NULL,
            state_stats_json TEXT NOT NULL,
            action_stats_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (dataset_id, generation_id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            dataset_id TEXT NOT NULL,
            generation_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            task_text TEXT,
            episode_count INTEGER NOT NULL,
            frame_count INTEGER NOT NULL,
            video_count INTEGER NOT NULL,
            duration_sec REAL NOT NULL,
            min_length INTEGER,
            p50_length REAL,
            p95_length REAL,
            max_length INTEGER,
            error_count INTEGER NOT NULL,
            warning_count INTEGER NOT NULL,
            info_count INTEGER NOT NULL,
            cameras_json TEXT NOT NULL,
            schema_json TEXT NOT NULL,
            state_stats_json TEXT NOT NULL,
            action_stats_json TEXT NOT NULL,
            PRIMARY KEY (dataset_id, generation_id, task_id)
        );

        CREATE TABLE IF NOT EXISTS episodes (
            dataset_id TEXT NOT NULL,
            generation_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            episode_index INTEGER NOT NULL,
            length INTEGER NOT NULL,
            fps REAL NOT NULL,
            duration_sec REAL NOT NULL,
            parquet_path TEXT NOT NULL,
            task_text TEXT,
            cameras_json TEXT NOT NULL,
            frame_start INTEGER,
            frame_end INTEGER,
            timestamp_start REAL,
            timestamp_end REAL,
            row_count INTEGER,
            error_count INTEGER NOT NULL,
            warning_count INTEGER NOT NULL,
            info_count INTEGER NOT NULL,
            state_stats_json TEXT NOT NULL,
            action_stats_json TEXT NOT NULL,
            PRIMARY KEY (dataset_id, generation_id, task_id, episode_index)
        );

        CREATE TABLE IF NOT EXISTS episode_videos (
            dataset_id TEXT NOT NULL,
            generation_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            episode_index INTEGER NOT NULL,
            camera_key TEXT NOT NULL,
            path TEXT NOT NULL,
            exists_flag INTEGER NOT NULL,
            width INTEGER,
            height INTEGER,
            fps REAL,
            duration_sec REAL,
            codec TEXT,
            nb_frames INTEGER,
            probe_error TEXT,
            PRIMARY KEY (dataset_id, generation_id, task_id, episode_index, camera_key)
        );

        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            generation_id INTEGER NOT NULL,
            task_id TEXT,
            episode_index INTEGER,
            severity TEXT NOT NULL,
            code TEXT NOT NULL,
            message TEXT NOT NULL,
            path TEXT,
            details_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_active
            ON tasks(dataset_id, generation_id, error_count, warning_count, task_id);
        CREATE INDEX IF NOT EXISTS idx_episodes_active
            ON episodes(dataset_id, generation_id, task_id, error_count, warning_count, episode_index);
        CREATE INDEX IF NOT EXISTS idx_health_active
            ON health_checks(dataset_id, generation_id, severity, task_id, episode_index);
        CREATE INDEX IF NOT EXISTS idx_runs_dataset
            ON index_runs(dataset_id, started_at DESC);
        """
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_load(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def insert_registered_datasets(conn: sqlite3.Connection, datasets: list[tuple[str, str, str]]) -> None:
    conn.executemany(
        """
        INSERT INTO datasets(id, name, root)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name, root=excluded.root
        """,
        datasets,
    )
    conn.commit()


def active_generation(conn: sqlite3.Connection, dataset_id: str) -> int | None:
    row = conn.execute(
        "SELECT active_generation_id FROM datasets WHERE id = ?",
        (dataset_id,),
    ).fetchone()
    if not row or row["active_generation_id"] is None:
        return None
    return int(row["active_generation_id"])

