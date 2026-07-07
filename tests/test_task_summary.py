from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lerobot_viewer.api import make_router
from lerobot_viewer.config import AppConfig, DatasetConfig, IndexConfig
from lerobot_viewer.db import connect, init_db, insert_registered_datasets, json_dump


def test_task_summary_returns_all_task_episode_counts(tmp_path: Path) -> None:
    root = tmp_path / "dataset"
    root.mkdir()
    db_path = tmp_path / "viewer.sqlite"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_registered_datasets(conn, [("dataset", "Dataset", str(root))])
        conn.execute(
            "INSERT INTO generations(id, dataset_id, created_at, is_smoke) VALUES (?, ?, ?, ?)",
            (1, "dataset", "2026-07-07T00:00:00Z", 0),
        )
        conn.execute("UPDATE datasets SET active_generation_id = ? WHERE id = ?", (1, "dataset"))
        for task_id, task_text, episode_count in [
            ("task_b", "Task B", 2),
            ("task_a", "Task A", 7),
            ("task_c", None, 1),
        ]:
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
                    "dataset",
                    1,
                    task_id,
                    task_text,
                    episode_count,
                    episode_count * 10,
                    0,
                    0.0,
                    None,
                    None,
                    None,
                    None,
                    0,
                    0,
                    0,
                    json_dump([]),
                    json_dump({}),
                    json_dump({}),
                    json_dump({}),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    app_config = AppConfig(
        datasets=[DatasetConfig(id="dataset", name="Dataset", root=root)],
        index=IndexConfig(),
        db_path=db_path,
    )
    app = FastAPI()
    app.include_router(make_router(app_config))

    response = TestClient(app).get("/api/datasets/dataset/task-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["episode_total"] == 10
    assert [(item["task_id"], item["episode_count"]) for item in payload["items"]] == [
        ("task_a", 7),
        ("task_b", 2),
        ("task_c", 1),
    ]
