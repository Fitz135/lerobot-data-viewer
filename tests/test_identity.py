from lerobot_viewer.identity import make_episode_uid, parse_episode_uid


def test_episode_uid_round_trip() -> None:
    uid = make_episode_uid("rdt_lerobot_v21", "arrange_word_ALOHA", 3)
    parsed = parse_episode_uid(uid)
    assert uid == "rdt_lerobot_v21/arrange_word_ALOHA/3"
    assert parsed.dataset_id == "rdt_lerobot_v21"
    assert parsed.task_id == "arrange_word_ALOHA"
    assert parsed.episode_index == 3

