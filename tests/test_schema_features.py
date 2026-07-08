import pyarrow as pa
import pyarrow.parquet as pq

from lerobot_viewer.indexer import (
    ACTION_FEATURE_PREFIXES,
    STATE_FEATURE_PREFIXES,
    feature_specs,
    read_parquet_summary,
)
from lerobot_viewer.timeseries import read_episode_timeseries


def test_feature_specs_uses_info_json_schema_prefixes() -> None:
    info = {
        "features": {
            "images.rgb.head": {"dtype": "video"},
            "states.joint.position": {"dtype": "float32", "shape": [2], "names": ["j0", "j1"]},
            "observation.states.effector.position": {"dtype": "float32", "shape": [1], "names": ["gripper"]},
            "actions.joint.position": {"dtype": "float32", "shape": [2], "names": ["j0", "j1"]},
            "master_actions.joint.position": {"dtype": "float32", "shape": [2], "names": ["j0", "j1"]},
            "timestamp": {"dtype": "float32", "shape": [1]},
        }
    }

    assert feature_specs(info, STATE_FEATURE_PREFIXES) == [
        ("states.joint.position", ["j0", "j1"]),
        ("observation.states.effector.position", ["gripper"]),
    ]
    assert feature_specs(info, ACTION_FEATURE_PREFIXES) == [
        ("actions.joint.position", ["j0", "j1"]),
        ("master_actions.joint.position", ["j0", "j1"]),
    ]


def test_read_parquet_summary_uses_dynamic_state_action_columns(tmp_path) -> None:
    path = tmp_path / "episode_000000.parquet"
    table = pa.table({
        "frame_index": pa.array([0, 1]),
        "timestamp": pa.array([0.0, 1.0 / 30.0]),
        "states.joint.position": pa.array([[1.0, 2.0], [1.5, 2.5]]),
        "actions.joint.position": pa.array([[3.0, 4.0], [3.5, 4.5]]),
    })
    pq.write_table(table, path)

    summary, checks = read_parquet_summary(
        path,
        [("states.joint.position", ["j0", "j1"])],
        [("actions.joint.position", ["j0", "j1"])],
        extreme_abs_value=1_000_000.0,
    )

    assert not [check for check in checks if check["code"] == "missing_parquet_columns"]
    assert summary["row_count"] == 2
    assert summary["state_stats"]["names"] == ["states.joint.position.j0", "states.joint.position.j1"]
    assert summary["action_stats"]["names"] == ["actions.joint.position.j0", "actions.joint.position.j1"]


def test_read_episode_timeseries_uses_dynamic_state_action_columns(tmp_path) -> None:
    path = tmp_path / "episode_000000.parquet"
    table = pa.table({
        "frame_index": pa.array([0, 1]),
        "timestamp": pa.array([0.0, 1.0 / 30.0]),
        "states.joint.position": pa.array([[1.0, 2.0], [1.5, 2.5]]),
        "actions.joint.position": pa.array([[3.0, 4.0], [3.5, 4.5]]),
    })
    pq.write_table(table, path)

    result = read_episode_timeseries(
        path,
        [("states.joint.position", ["j0", "j1"])],
        [("actions.joint.position", ["j0", "j1"])],
    )

    assert result["series"]["states.joint.position.j0"] == [1.0, 1.5]
    assert result["series"]["actions.joint.position.j1"] == [4.0, 4.5]
