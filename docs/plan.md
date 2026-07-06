# LeRobot Data Viewer Plan

## Goal

Build a local read-only visualization tool for LeRobot v2.1 training data.
The first registered dataset is:

`/inspire/qb-ilm/project/semantic-visual-tokenizer/public/wam/data_processed/rdt_lerobot_v21`

The tool must support both macro dashboard inspection and episode-level quality
inspection.

## Non-Goals

- No mutation of source LeRobot datasets.
- No first-version annotation or bad-sample writeback.
- No login system.
- No arbitrary raw dataset adapters beyond LeRobot v2.1.
- No embedding clustering or automatic action-quality classifier in MVP.

## Architecture

- Frontend: Vite, React, TypeScript, uPlot.
- Backend: FastAPI, SQLite cache, pyarrow parquet reads, ffprobe video probing.
- Runtime: local by default, bound to `127.0.0.1`.
- Data access: datasets are explicitly registered in `config/datasets.yaml`.
- Media access: video files are served through backend endpoints with Range
  support and registry-root path checks.

## Identity

Stable public identity uses:

```text
dataset_id = registry dataset id
task_id = LeRobot task directory name
episode_index = LeRobot episode index
episode_uid = dataset_id/task_id/episode_index
```

SQLite may use internal row ids, but APIs and URLs use stable identity.

## Cache Model

SQLite stores metadata, statistics, health checks, file paths, and ffprobe
summaries. It does not store complete frame-level state/action arrays.

Refresh uses generations:

1. A refresh creates a new `generation_id` and `index_run`.
2. Rows for the new generation are written while the old active generation
   remains visible.
3. On success, one transaction switches `datasets.active_generation_id`.
4. On failure, the previous generation remains active and the failed run is
   inspectable.

## Dashboard

Global dashboard:

- dataset count
- task count
- episode count
- frame count
- video count
- duration
- error/warning/info totals

Dataset detail:

- task table
- length distribution summary
- camera/schema summary
- health-check aggregation
- refresh state

Task detail:

- episode table with paging/filtering
- length and issue summary
- links into episode browser

## Episode Browser

The browser uses `frame_index` as the single master clock.

- Dynamic camera list from `meta/info.json` video features.
- Three-camera Agilex layout is optimized but not hard-coded in data logic.
- Video seek uses `frame_index / fps`.
- `observation.state` and `action` are separate uPlot charts.
- Full single-episode timeseries JSON is loaded on entry, with optional
  downsampling support for long episodes.

## Health Checks

Severity:

- `error`: blocks useful browsing/training.
- `warning`: suspicious but still browseable.
- `info`: statistical or low-risk notice.

Initial checks:

- missing metadata, parquet, or video files
- parquet row count mismatch
- missing expected columns
- NaN/Inf in state/action
- all-zero/all-constant state/action episodes
- extreme numeric values
- video ffprobe failure
- video fps/duration/shape mismatch

Initial video duration tolerance:

- absolute difference greater than `0.5s`, or
- relative difference greater than `2%`

## API Draft

```text
GET  /api/health
GET  /api/datasets
GET  /api/datasets/{dataset_id}
GET  /api/datasets/{dataset_id}/tasks
GET  /api/datasets/{dataset_id}/tasks/{task_id}
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}/timeseries
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}/videos/{camera_key}
POST /api/datasets/{dataset_id}/refresh
GET  /api/index-runs
```

## Acceptance

1. `make index` builds a complete SQLite cache for `rdt_lerobot_v21`.
2. Global dashboard shows task, episode, frame, video, and issue totals.
3. Dataset detail shows task table, length summary, schema/camera summary, and
   health-check aggregation.
4. Task detail supports issue/length browsing and opens an episode.
5. Episode browser opens `arrange_word_ALOHA/episode_000000`, synchronizes
   videos by frame index, and shows state/action curves.
6. Media endpoints cannot read outside registered dataset roots.
7. Failed refresh keeps old active cache intact.
8. Tests cover path whitelist, stable ids, health checks, and timeseries shape.

