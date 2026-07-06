from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from .config import AppConfig, ensure_path_in_dataset
from .db import active_generation, connect, init_db, insert_registered_datasets, json_load, row_to_dict
from .identity import make_episode_uid
from .indexer import index_dataset
from .timeseries import read_episode_timeseries


@dataclass(frozen=True)
class EpisodeSearchQuery:
    task_id: str | None
    episode_index: int | None
    dataset_matches: bool = True


def parse_episode_search_query(dataset_id: str, query: str) -> EpisodeSearchQuery:
    text = query.strip()
    parts = [part for part in text.split("/") if part]
    if len(parts) == 3:
        return EpisodeSearchQuery(
            task_id=parts[1],
            episode_index=parse_episode_index(parts[2]),
            dataset_matches=parts[0] == dataset_id,
        )
    if len(parts) == 2:
        return EpisodeSearchQuery(task_id=parts[0], episode_index=parse_episode_index(parts[1]))
    return EpisodeSearchQuery(task_id=None, episode_index=parse_episode_index(text))


def parse_episode_index(value: str) -> int | None:
    match = re.fullmatch(r"(?:episode_)?0*(\d+)(?:\.(?:parquet|mp4))?", value.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def make_router(app_config: AppConfig) -> APIRouter:
    router = APIRouter(prefix="/api")
    running_lock = threading.Lock()
    running: set[str] = set()

    def conn_scope() -> Any:
        conn = connect(app_config.db_path)
        init_db(conn)
        insert_registered_datasets(conn, [(item.id, item.name, str(item.root)) for item in app_config.datasets])
        return conn

    def dataset_or_404(dataset_id: str) -> Any:
        try:
            return app_config.dataset(dataset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_id}") from exc

    def require_generation(conn: Any, dataset_id: str) -> int:
        generation_id = active_generation(conn, dataset_id)
        if generation_id is None:
            raise HTTPException(status_code=404, detail="Dataset has no active index generation")
        return generation_id

    def decode_row(row: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        for key in list(decoded.keys()):
            if key.endswith("_json"):
                decoded[key[:-5]] = json_load(decoded.pop(key), {})
        return decoded

    def get_episode_row(conn: Any, dataset_id: str, task_id: str, episode_index: int) -> tuple[int, dict[str, Any]]:
        generation_id = require_generation(conn, dataset_id)
        row = conn.execute(
            """
            SELECT * FROM episodes
            WHERE dataset_id = ? AND generation_id = ? AND task_id = ? AND episode_index = ?
            """,
            (dataset_id, generation_id, task_id, episode_index),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        return generation_id, decode_row(row_to_dict(row) or {})

    @router.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "db_path": str(app_config.db_path)}

    @router.get("/datasets")
    def list_datasets() -> dict[str, Any]:
        conn = conn_scope()
        try:
            rows = conn.execute(
                """
                SELECT d.*, s.task_count, s.episode_count, s.frame_count,
                       s.video_count, s.duration_sec, s.error_count,
                       s.warning_count, s.info_count, g.is_smoke
                FROM datasets d
                LEFT JOIN dataset_stats s
                  ON s.dataset_id = d.id AND s.generation_id = d.active_generation_id
                LEFT JOIN generations g
                  ON g.id = d.active_generation_id
                ORDER BY d.id
                """
            ).fetchall()
            datasets: list[dict[str, Any]] = []
            for row in rows:
                item = row_to_dict(row) or {}
                item["root_exists"] = Path(item["root"]).exists()
                datasets.append(item)
            return {"datasets": datasets}
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}")
    def dataset_detail(dataset_id: str) -> dict[str, Any]:
        dataset = dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            row = conn.execute(
                """
                SELECT d.*, s.*
                FROM datasets d
                LEFT JOIN dataset_stats s
                  ON s.dataset_id = d.id AND s.generation_id = d.active_generation_id
                WHERE d.id = ?
                """,
                (dataset_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Dataset not found")
            item = decode_row(row_to_dict(row) or {})
            item["root_exists"] = dataset.root.exists()
            return item
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/tasks")
    def list_tasks(
        dataset_id: str,
        search: str | None = None,
        issue: str | None = Query(default=None, pattern="^(error|warning|any)$"),
        sort: str = "issues",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            generation_id = require_generation(conn, dataset_id)
            where = ["dataset_id = ?", "generation_id = ?"]
            params: list[Any] = [dataset_id, generation_id]
            if search:
                where.append("(task_id LIKE ? OR COALESCE(task_text, '') LIKE ?)")
                like = f"%{search}%"
                params.extend([like, like])
            if issue == "error":
                where.append("error_count > 0")
            elif issue == "warning":
                where.append("warning_count > 0")
            elif issue == "any":
                where.append("(error_count > 0 OR warning_count > 0)")
            order_by = {
                "issues": "error_count DESC, warning_count DESC, episode_count DESC, task_id ASC",
                "episodes": "episode_count DESC, task_id ASC",
                "frames": "frame_count DESC, task_id ASC",
                "p95": "p95_length DESC, task_id ASC",
                "name": "task_id ASC",
            }.get(sort, "error_count DESC, warning_count DESC, episode_count DESC, task_id ASC")
            where_sql = " AND ".join(where)
            total = conn.execute(f"SELECT COUNT(*) AS count FROM tasks WHERE {where_sql}", params).fetchone()["count"]
            rows = conn.execute(
                f"""
                SELECT * FROM tasks
                WHERE {where_sql}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                params + [page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [decode_row(row_to_dict(row) or {}) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/tasks/{task_id}")
    def task_detail(dataset_id: str, task_id: str) -> dict[str, Any]:
        dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            generation_id = require_generation(conn, dataset_id)
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE dataset_id = ? AND generation_id = ? AND task_id = ?
                """,
                (dataset_id, generation_id, task_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Task not found")
            return decode_row(row_to_dict(row) or {})
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/episodes/search")
    def search_episodes(
        dataset_id: str,
        q: str = Query(..., min_length=1),
        page_size: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        dataset_or_404(dataset_id)
        parsed = parse_episode_search_query(dataset_id, q)
        if not parsed.dataset_matches or parsed.episode_index is None:
            return {"items": [], "page": 1, "page_size": page_size, "total": 0}

        conn = conn_scope()
        try:
            generation_id = require_generation(conn, dataset_id)
            where = ["dataset_id = ?", "generation_id = ?", "episode_index = ?"]
            params: list[Any] = [dataset_id, generation_id, parsed.episode_index]
            if parsed.task_id:
                where.append("task_id = ?")
                params.append(parsed.task_id)
            where_sql = " AND ".join(where)
            total = conn.execute(f"SELECT COUNT(*) AS count FROM episodes WHERE {where_sql}", params).fetchone()["count"]
            rows = conn.execute(
                f"""
                SELECT * FROM episodes
                WHERE {where_sql}
                ORDER BY task_id ASC, episode_index ASC
                LIMIT ?
                """,
                params + [page_size],
            ).fetchall()
            return {
                "items": [decode_row(row_to_dict(row) or {}) for row in rows],
                "page": 1,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/tasks/{task_id}/episodes")
    def list_episodes(
        dataset_id: str,
        task_id: str,
        issue: str | None = Query(default=None, pattern="^(error|warning|any)$"),
        sort: str = "episode",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            generation_id = require_generation(conn, dataset_id)
            where = ["dataset_id = ?", "generation_id = ?", "task_id = ?"]
            params: list[Any] = [dataset_id, generation_id, task_id]
            if issue == "error":
                where.append("error_count > 0")
            elif issue == "warning":
                where.append("warning_count > 0")
            elif issue == "any":
                where.append("(error_count > 0 OR warning_count > 0)")
            order_by = {
                "episode": "episode_index ASC",
                "length": "length DESC, episode_index ASC",
                "issues": "error_count DESC, warning_count DESC, episode_index ASC",
            }.get(sort, "episode_index ASC")
            where_sql = " AND ".join(where)
            total = conn.execute(f"SELECT COUNT(*) AS count FROM episodes WHERE {where_sql}", params).fetchone()["count"]
            rows = conn.execute(
                f"""
                SELECT * FROM episodes
                WHERE {where_sql}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                params + [page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [decode_row(row_to_dict(row) or {}) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}")
    def episode_detail(dataset_id: str, task_id: str, episode_index: int) -> dict[str, Any]:
        dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            generation_id, episode = get_episode_row(conn, dataset_id, task_id, episode_index)
            videos = conn.execute(
                """
                SELECT * FROM episode_videos
                WHERE dataset_id = ? AND generation_id = ? AND task_id = ? AND episode_index = ?
                ORDER BY camera_key
                """,
                (dataset_id, generation_id, task_id, episode_index),
            ).fetchall()
            checks = conn.execute(
                """
                SELECT severity, code, message, path, details_json
                FROM health_checks
                WHERE dataset_id = ? AND generation_id = ? AND task_id = ? AND episode_index = ?
                ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, code
                """,
                (dataset_id, generation_id, task_id, episode_index),
            ).fetchall()
            episode["uid"] = make_episode_uid(dataset_id, task_id, episode_index)
            return {
                "episode": episode,
                "videos": [row_to_dict(row) for row in videos],
                "health_checks": [decode_row(row_to_dict(row) or {}) for row in checks],
            }
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}/timeseries")
    def episode_timeseries(
        dataset_id: str,
        task_id: str,
        episode_index: int,
        downsample: int | None = Query(default=None, ge=1),
    ) -> dict[str, Any]:
        dataset = dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            generation_id, episode = get_episode_row(conn, dataset_id, task_id, episode_index)
            task = conn.execute(
                """
                SELECT schema_json FROM tasks
                WHERE dataset_id = ? AND generation_id = ? AND task_id = ?
                """,
                (dataset_id, generation_id, task_id),
            ).fetchone()
            schema = json_load(task["schema_json"], {}) if task else {}
            state_names = ((schema.get("state") or {}).get("names")) or []
            action_names = ((schema.get("action") or {}).get("names")) or []
            parquet_path = ensure_path_in_dataset(dataset, episode["parquet_path"])
            if not parquet_path.exists():
                raise HTTPException(status_code=404, detail="Parquet file is missing")
            return read_episode_timeseries(parquet_path, state_names, action_names, downsample)
        finally:
            conn.close()

    @router.get("/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}/videos/{camera_key}")
    def episode_video(
        dataset_id: str,
        task_id: str,
        episode_index: int,
        camera_key: str,
        request: Request,
    ) -> Response:
        dataset = dataset_or_404(dataset_id)
        conn = conn_scope()
        try:
            generation_id = require_generation(conn, dataset_id)
            row = conn.execute(
                """
                SELECT path FROM episode_videos
                WHERE dataset_id = ? AND generation_id = ? AND task_id = ?
                  AND episode_index = ? AND camera_key = ?
                """,
                (dataset_id, generation_id, task_id, episode_index, camera_key),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Video not found")
            path = ensure_path_in_dataset(dataset, row["path"])
            if not path.exists():
                raise HTTPException(status_code=404, detail="Video file is missing")
            return ranged_file_response(path, request)
        finally:
            conn.close()

    @router.post("/datasets/{dataset_id}/refresh")
    def refresh_dataset(
        dataset_id: str,
        smoke: bool = False,
        max_tasks: int | None = None,
        max_episodes_per_task: int | None = None,
    ) -> dict[str, Any]:
        dataset_or_404(dataset_id)
        with running_lock:
            if dataset_id in running:
                return {"status": "already_running", "dataset_id": dataset_id}
            running.add(dataset_id)

        def run() -> None:
            try:
                index_dataset(
                    app_config,
                    dataset_id,
                    smoke=smoke,
                    max_tasks=max_tasks,
                    max_episodes_per_task=max_episodes_per_task,
                )
            finally:
                with running_lock:
                    running.discard(dataset_id)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return {"status": "started", "dataset_id": dataset_id}

    @router.get("/index-runs")
    def index_runs(dataset_id: str | None = None, limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        conn = conn_scope()
        try:
            params: list[Any] = []
            where = ""
            if dataset_id:
                where = "WHERE dataset_id = ?"
                params.append(dataset_id)
            rows = conn.execute(
                f"""
                SELECT * FROM index_runs
                {where}
                ORDER BY started_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
            runs = [row_to_dict(row) for row in rows]
            if runs:
                run_ids = [run["id"] for run in runs]
                placeholders = ",".join("?" for _ in run_ids)
                events = conn.execute(
                    f"""
                    SELECT * FROM index_events
                    WHERE run_id IN ({placeholders})
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    run_ids,
                ).fetchall()
                event_rows = [row_to_dict(row) for row in events]
            else:
                event_rows = []
            return {"runs": runs, "events": event_rows}
        finally:
            conn.close()

    return router


def ranged_file_response(path: Path, request: Request) -> Response:
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    headers = {"Accept-Ranges": "bytes"}
    if not range_header:
        return FileResponse(path, media_type="video/mp4", headers=headers)
    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid Range header")
    range_spec = range_header.removeprefix("bytes=").split(",", 1)[0]
    start_text, _, end_text = range_spec.partition("-")
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
    else:
        suffix = int(end_text)
        start = max(file_size - suffix, 0)
        end = file_size - 1
    if start < 0 or end >= file_size or start > end:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")
    length = end - start + 1
    headers.update(
        {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Content-Type": "video/mp4",
        }
    )
    return StreamingResponse(
        iter_file_range(path, start, end),
        status_code=206,
        media_type="video/mp4",
        headers=headers,
    )


def iter_file_range(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024) -> Any:
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
