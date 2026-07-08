from pathlib import Path

from lerobot_viewer.indexer import discover_task_dirs, task_id_for_root


def make_task(root: Path) -> None:
    meta = root / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text("{}")
    (meta / "episodes.jsonl").write_text("")


def test_discover_flat_task_dirs_preserves_task_id(tmp_path: Path) -> None:
    make_task(tmp_path / "arrange_word_ALOHA")

    task_dirs = discover_task_dirs(tmp_path)

    assert task_dirs == [tmp_path / "arrange_word_ALOHA"]
    assert task_id_for_root(tmp_path, task_dirs[0]) == "arrange_word_ALOHA"


def test_discover_grouped_task_dirs_uses_route_safe_task_id(tmp_path: Path) -> None:
    make_task(tmp_path / "real" / "Pickup_a_bottle")
    make_task(tmp_path / "sim" / "basic_tasks-split_aloha")

    task_dirs = discover_task_dirs(tmp_path)

    assert task_dirs == [
        tmp_path / "real" / "Pickup_a_bottle",
        tmp_path / "sim" / "basic_tasks-split_aloha",
    ]
    assert [task_id_for_root(tmp_path, path) for path in task_dirs] == [
        "real__Pickup_a_bottle",
        "sim__basic_tasks-split_aloha",
    ]
