from lerobot_viewer.api import parse_episode_search_query


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

