from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lerobot_viewer.api import make_router
from lerobot_viewer.config import AppConfig, DatasetConfig, IndexConfig
from lerobot_viewer.db import connect, init_db, insert_registered_datasets, json_dump


def make_client(tmp_path: Path) -> TestClient:
    root = tmp_path / "dataset"
    root.mkdir()
    db_path = tmp_path / "viewer.sqlite"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_registered_datasets(conn, [("dataset", "Dataset", str(root))])
        conn.execute(
            "INSERT INTO generations(id, dataset_id, created_at, is_smoke) VALUES (?, ?, ?, ?)",
            (1, "dataset", "2026-07-08T00:00:00Z", 0),
        )
        conn.execute("UPDATE datasets SET active_generation_id = ? WHERE id = ?", (1, "dataset"))
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
                "dataset",
                1,
                1,
                1,
                30,
                2,
                1.0,
                0,
                0,
                0,
                json_dump([]),
                json_dump({}),
                json_dump({}),
                json_dump({}),
                "2026-07-08T00:00:00Z",
            ),
        )
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
                "task_a",
                "Task A",
                1,
                30,
                2,
                1.0,
                30,
                30.0,
                30.0,
                30,
                0,
                0,
                0,
                json_dump([]),
                json_dump({}),
                json_dump({}),
                json_dump({}),
            ),
        )
        for camera_key, duration_sec in [("head", 1.25), ("hand", 1.5)]:
            conn.execute(
                """
                INSERT INTO episode_videos(
                    dataset_id, generation_id, task_id, episode_index, camera_key, path,
                    exists_flag, width, height, fps, duration_sec, codec, nb_frames, probe_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "dataset",
                    1,
                    "task_a",
                    0,
                    camera_key,
                    f"/{camera_key}.mp4",
                    1,
                    None,
                    None,
                    30.0,
                    duration_sec,
                    "h264",
                    None,
                    None,
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
    return TestClient(app)


def test_dataset_responses_include_video_duration(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    datasets = client.get("/api/datasets").json()["datasets"]
    detail = client.get("/api/datasets/dataset").json()

    assert datasets[0]["duration_sec"] == 1.0
    assert datasets[0]["video_duration_sec"] == 2.75
    assert detail["duration_sec"] == 1.0
    assert detail["video_duration_sec"] == 2.75


def test_task_responses_include_video_duration(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    tasks = client.get("/api/datasets/dataset/tasks").json()["items"]
    detail = client.get("/api/datasets/dataset/tasks/task_a").json()

    assert tasks[0]["duration_sec"] == 1.0
    assert tasks[0]["video_duration_sec"] == 2.75
    assert detail["duration_sec"] == 1.0
    assert detail["video_duration_sec"] == 2.75
