from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpisodeUid:
    dataset_id: str
    task_id: str
    episode_index: int

    def as_string(self) -> str:
        return f"{self.dataset_id}/{self.task_id}/{self.episode_index}"


def make_episode_uid(dataset_id: str, task_id: str, episode_index: int) -> str:
    return EpisodeUid(dataset_id, task_id, int(episode_index)).as_string()


def parse_episode_uid(value: str) -> EpisodeUid:
    parts = value.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid episode uid: {value}")
    dataset_id, task_id, episode_text = parts
    return EpisodeUid(dataset_id=dataset_id, task_id=task_id, episode_index=int(episode_text))

