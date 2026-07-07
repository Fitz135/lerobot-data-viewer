from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lerobot_viewer.api import make_router, parse_episode_search_query
from lerobot_viewer.config import AppConfig, DatasetConfig, IndexConfig
from lerobot_viewer.db import connect, init_db, insert_registered_datasets, json_dump


def test_parse_episode_search_by_plain_index() -> None:
    parsed = parse_episode_search_query("dataset", "12")

    assert parsed.task_id is None
    assert parsed.episode_index == 12
    assert parsed.dataset_matches


def test_parse_episode_search_by_episode_filename() -> None:
    parsed = parse_episode_search_query("dataset", "episode_000012.parquet")

    assert parsed.task_id is None
    assert parsed.episode_index == 12
    assert parsed.dataset_matches


def test_parse_episode_search_by_task_and_index() -> None:
    parsed = parse_episode_search_query("dataset", "arrange_word_ALOHA/episode_000012")

    assert parsed.task_id == "arrange_word_ALOHA"
    assert parsed.episode_index == 12
    assert parsed.dataset_matches


def test_parse_episode_search_rejects_other_dataset_uid() -> None:
    parsed = parse_episode_search_query("dataset", "other/arrange_word_ALOHA/12")

    assert parsed.task_id == "arrange_word_ALOHA"
    assert parsed.episode_index == 12
    assert not parsed.dataset_matches


def test_episode_search_without_query_returns_example_episodes(tmp_path: Path) -> None:
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
        episodes = [
            ("task_b", 0),
            ("task_a", 2),
            ("task_a", 0),
        ]
        for task_id, episode_index in episodes:
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
                    "dataset",
                    1,
                    task_id,
                    episode_index,
                    10,
                    30.0,
                    0.33,
                    str(root / task_id / f"episode_{episode_index:06d}.parquet"),
                    None,
                    json_dump([]),
                    0,
                    9,
                    0.0,
                    0.3,
                    10,
                    0,
                    0,
                    0,
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

    response = TestClient(app).get("/api/datasets/dataset/episodes/search?page_size=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert [(item["task_id"], item["episode_index"]) for item in payload["items"]] == [
        ("task_a", 0),
        ("task_a", 2),
    ]
