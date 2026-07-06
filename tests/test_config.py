from pathlib import Path

import pytest

from lerobot_viewer.config import DatasetConfig, ensure_path_in_dataset


def test_path_must_stay_under_dataset_root(tmp_path: Path) -> None:
    root = tmp_path / "dataset"
    root.mkdir()
    inside = root / "task" / "video.mp4"
    inside.parent.mkdir()
    inside.write_bytes(b"")
    dataset = DatasetConfig(id="test", name="Test", root=root)

    assert ensure_path_in_dataset(dataset, inside) == inside.resolve()

    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"")
    with pytest.raises(ValueError):
        ensure_path_in_dataset(dataset, outside)

