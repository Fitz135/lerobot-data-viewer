# Changelog

## 2026-07-08

### Added

- Registered `intern_data_a1` as a second dataset root.
- Added task discovery for LeRobot roots grouped one level below category
  directories such as `real/` and `sim/`.
- Added `video_duration_sec` to dataset and task API responses so UI can
  distinguish episode duration from summed mp4 duration.
- Switched state/action parquet validation and timeseries loading from fixed
  `observation.state` / `action` columns to task-local `meta/info.json`
  schemas, fixing false `missing_parquet_columns` errors for `intern_data_a1`.

## 2026-07-06

### Added

- Created the initial LeRobot Data Viewer project with FastAPI, SQLite cache,
  Vite/React frontend, and uPlot charts.
- Added `config/datasets.yaml` with `rdt_lerobot_v21` as the first registered
  LeRobot v2.1 dataset.
- Added smoke and full indexing commands:
  - `make index-smoke`
  - `make index`
- Added generation-based SQLite refresh so a failed refresh does not replace
  the previous active index.
- Added GitHub Pages deployment for the static frontend:
  `https://fitz135.github.io/lerobot-data-viewer/`.
- Added runtime API base configuration through the top-right `Set API` field
  and the `?api=<backend>/api` URL parameter.
- Added VS Code proxy startup script:
  `scripts/start_server.sh`.
- Added dataset-level episode id lookup on the dataset detail page.

### Changed

- Dataset refresh polling runs only after a user-triggered smoke/full refresh.
  It polls `index-runs`, refreshes dashboard/task data once after the
  triggered run finishes, and then stops.
- `scripts/start_server.sh` reuses an already healthy backend on the chosen port
  and gives a clear message when the port is occupied by another process.
- GitHub Pages frontend has been rebuilt and published after frontend changes.

### Episode Lookup Query Forms

```text
12
episode_000012
episode_000012.parquet
task_id/12
task_id/episode_000012
dataset_id/task_id/12
```

Plain episode indexes search across all tasks in the current dataset. Queries
with a task id search within that task.

### Verification

- `make test` passes with backend tests and frontend build.
- Episode search parser tests cover plain ids, `episode_000012` style ids,
  task-qualified ids, and mismatched dataset ids.
