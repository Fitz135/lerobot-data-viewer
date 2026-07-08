# Functional Requirements

This document records the current product requirements for LeRobot Data Viewer.
Keep it as a current-state requirements reference, not as a per-change log.
Update it whenever a code change adds, removes, or changes behavior.

## Scope

LeRobot Data Viewer is a local, read-only dashboard and episode browser for
registered LeRobot v2.1 datasets.

Registered datasets are configured in `config/datasets.yaml` and currently include:

```text
rdt_lerobot_v21
intern_data_a1
```

## Core Requirements

- The application must never modify registered LeRobot dataset roots.
- Dataset roots must be explicitly registered in `config/datasets.yaml`.
- Public dataset, task, and episode identities must use stable values:
  `dataset_id`, `task_id`, and `episode_index`.
- Backend media and parquet access must reject paths outside the registered
  dataset root.
- The local SQLite cache must be generation-based so failed refreshes do not
  replace the previous active index.
- The frontend must work locally against `http://127.0.0.1:8000/api` by default
  and must allow runtime API base configuration for GitHub Pages.

## Dashboard Requirements

Global dashboard:

- Show all registered datasets.
- Show aggregate dataset, task, episode, frame, video, episode-duration,
  video-duration, error, and warning counts.
- Link each dataset to its dataset detail page.

Dataset detail:

- Show dataset root and root existence state.
- Show task, episode, frame, video, episode-duration, video-duration, error,
  and warning totals.
- Show recent index run status and progress.
- Provide `Smoke Refresh` and `Full Refresh` actions.
- Poll only for a user-triggered refresh and stop after the tracked run
  completes.
- Show a `task` section listing all tasks and each task's episode count.
- Provide task filtering by text/id and issue status.
- Provide episode lookup using a task selector plus an episode id input.

Task detail:

- Show task text and task-level counts/statistics.
- List episodes with issue filtering and sorting by episode, length, or issues.
- Link each episode to the episode browser.

## Episode Lookup Requirements

Dataset-level episode lookup must support these query forms at the API level:

```text
12
episode_000012
episode_000012.parquet
task_id/12
task_id/episode_000012
dataset_id/task_id/12
```

The current dataset page UI uses a task dropdown plus an episode id field, then
sends `task_id/episode_id` to the API.

If a query includes a mismatched dataset id or an unparsable episode id, the API
must return an empty result set rather than a different dataset's episode.

## Episode Browser Requirements

- Open episodes from stable hash routes.
- Show available videos for the episode.
- Serve videos through backend endpoints with Range request support.
- Use `frame_index` as the master clock.
- Seek videos by `frame_index / fps`.
- Keep multiple videos synchronized during playback.
- Show `observation.state` and `action` uPlot charts.
- Load full timeseries for a single episode with optional downsampling for
  browser performance.
- Show episode health checks and source file paths.

## Indexing And Health Requirements

Indexing must:

- Read task metadata from LeRobot task directories.
- Discover task directories that are either direct children of a registered root
  or one level below grouping directories such as `real/` and `sim/`.
- Read parquet summaries for required columns: `frame_index`, `timestamp`,
  `observation.state`, and `action`.
- Probe videos with `ffprobe`.
- Store dataset, task, episode, video, and health-check summaries in SQLite.
- Report episode duration separately from summed per-file video duration.
- Aggregate state/action statistics at episode, task, and dataset levels.
- Record index run progress and recent index events.

Health checks must cover:

- missing metadata, parquet, or video files
- parquet read failures
- parquet row count mismatch
- missing required parquet columns
- NaN/Inf in state/action
- all-zero or all-constant state/action values
- constant state/action dimensions
- extreme numeric values
- ffprobe failures
- video width, height, fps, and duration mismatches

## Public Frontend Requirements

- The static frontend is published at
  `https://fitz135.github.io/lerobot-data-viewer/`.
- Public frontend usage requires a reachable backend URL passed through the
  `?api=<backend>/api` query parameter or set in the top-right API field.
- Frontend-visible changes must be rebuilt with
  `make frontend-build-public PUBLIC_BASE_PATH=/lerobot-data-viewer/` and
  deployed to `gh-pages`.
- The backend should be exposed over HTTPS for public frontend use to avoid
  browser mixed-content blocking.

## Maintenance Requirements

- After each completed new requirement, commit and push source changes to
  `main`.
- If the requirement changes the public frontend, also push the generated
  frontend deployment to `gh-pages`.
- Whenever code changes, review and update `docs/code-structure.md` and this
  document in the same change so they remain synchronized with the
  implementation.
- `.AGENT.md` must contain standing workflow rules only, not a per-change log.
