from __future__ import annotations

import argparse

from .config import load_config
from .indexer import index_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lerobot-data-viewer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", help="Index a registered LeRobot dataset")
    index.add_argument("--dataset", required=True, help="Dataset id from config/datasets.yaml")
    index.add_argument("--deep", action="store_true", help="Run deep checks. Present for explicit CLI readability.")
    index.add_argument("--smoke", action="store_true", help="Index a small subset for fast validation")
    index.add_argument("--max-tasks", type=int, default=None)
    index.add_argument("--max-episodes-per-task", type=int, default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    app_config = load_config()
    if args.command == "index":
        run_id = index_dataset(
            app_config,
            args.dataset,
            smoke=args.smoke,
            max_tasks=args.max_tasks,
            max_episodes_per_task=args.max_episodes_per_task,
        )
        print(f"index_run_id={run_id}")


if __name__ == "__main__":
    main()

