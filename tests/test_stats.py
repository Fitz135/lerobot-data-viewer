from lerobot_viewer.stats import compute_matrix_stats


def test_matrix_stats_detects_nan_inf_and_extreme_values() -> None:
    stats = compute_matrix_stats(
        [[0.0, 1.0], [float("nan"), 1_000_001.0], [float("inf"), 3.0]],
        ["a", "b"],
        extreme_abs_value=1_000_000.0,
    ).to_dict()

    assert stats["nan_count"] == 1
    assert stats["inf_count"] == 1
    assert stats["extreme_count"] == 1
    assert stats["names"] == ["a", "b"]

