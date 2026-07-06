from lerobot_viewer.timeseries import _downsample_indices, _series_from_matrix


def test_downsample_indices_preserves_endpoints() -> None:
    assert _downsample_indices(10, 4) == [0, 3, 6, 9]


def test_series_shape_uses_feature_names() -> None:
    series = _series_from_matrix([[1.0, 2.0], [3.0, 4.0]], ["left", "right"], "action", [0, 1])

    assert series == {
        "action.left": [1.0, 3.0],
        "action.right": [2.0, 4.0],
    }

