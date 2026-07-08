# Code Structure

This document records the current source layout and ownership boundaries for
LeRobot Data Viewer. Update it when code moves, new modules are added, API
surfaces change, or frontend views are restructured.

## Top-Level Layout

```text
backend/                  FastAPI backend package and local SQLite cache
config/datasets.yaml      Explicit dataset registry and index settings
docs/                     Project design, deployment, structure, and requirements
scripts/start_server.sh   Helper for VS Code proxy/public frontend backend startup
tests/                    Backend unit and integration tests
web/                      Vite/React frontend
Makefile                  Common install, run, index, test, and build commands
pyproject.toml            Python dependencies and pytest configuration
```

Generated/runtime data:

- `backend/data/viewer.sqlite` is the local SQLite index cache.
- `web/dist/` is the frontend build output.
- `.uv-cache/` and `.npm-cache/` are local dependency caches used by Makefile
  targets.

## Backend Package

`backend/lerobot_viewer/` contains the Python backend:

- `main.py` creates the FastAPI app, configures CORS from
  `LDRV_CORS_ORIGINS`, and mounts the API router.
- `api.py` defines all `/api` endpoints, request parsing, dataset/task/episode
  lookup, index refresh triggering, timeseries loading, and Range video
  streaming.
- `config.py` loads `config/datasets.yaml`, supports `LDRV_CONFIG` and
  `LDRV_DB_PATH`, and enforces registered dataset-root path checks.
- `db.py` owns SQLite connection setup, schema creation, JSON helpers, dataset
  registration, and active-generation lookup.
- `indexer.py` discovers registered LeRobot v2.1 task directories from either
  flat dataset roots or one-level grouped roots such as `real/` and `sim/`,
  reads metadata and parquet summaries, probes videos with `ffprobe`, writes
  health checks, aggregates task/dataset stats, and activates successful
  generations.
- `timeseries.py` reads per-episode parquet frame, timestamp, state, and action
  series with optional downsampling.
- `stats.py` computes numeric summaries for state/action matrices.
- `identity.py` builds and parses stable `dataset_id/task_id/episode_index`
  episode identifiers.
- `cli.py` exposes the `index` command used by `make index` and
  `make index-smoke`.

## API Surface

The router is mounted under `/api`:

```text
GET  /api/health
GET  /api/datasets
GET  /api/datasets/{dataset_id}
GET  /api/datasets/{dataset_id}/tasks
GET  /api/datasets/{dataset_id}/task-summary
GET  /api/datasets/{dataset_id}/tasks/{task_id}
GET  /api/datasets/{dataset_id}/episodes/search
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}/timeseries
GET  /api/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}/videos/{camera_key}
POST /api/datasets/{dataset_id}/refresh
GET  /api/index-runs
```

The video endpoint validates paths against the registered dataset root and
supports HTTP Range requests for browser playback.

## SQLite Cache Model

The local cache is generation-based. A refresh writes a new generation while the
old active generation remains visible. Only after a successful scan does the
backend update `datasets.active_generation_id`.

Main tables:

- `datasets`, `generations`
- `index_runs`, `index_events`
- `dataset_stats`
- `tasks`
- `episodes`
- `episode_videos`
- `health_checks`

## Frontend Structure

`web/src/` contains the React app:

- `main.tsx` implements hash routing, page components, task/episode tables,
  refresh controls, episode browser, synchronized video playback, and uPlot
  timeseries charts.
- `api.ts` owns runtime API base selection from `?api=...`, `localStorage`, or
  `VITE_API_BASE`, plus `GET`, `POST`, and video URL helpers.
- `types.ts` mirrors backend response shapes used by the UI.
- `styles.css` defines the dashboard, table, toolbar, video, and plot layout.

Current hash routes:

```text
#/
#/datasets/{dataset_id}
#/datasets/{dataset_id}/tasks/{task_id}
#/datasets/{dataset_id}/tasks/{task_id}/episodes/{episode_index}
```

## Tests

`tests/` focuses on backend behavior:

- config and registered-root path validation
- stable episode identity
- stats and timeseries shape
- episode search parsing and lookup behavior
- dataset task summary behavior
- flat and grouped LeRobot task directory discovery

`make test` runs `uv run pytest` and the frontend TypeScript/Vite build.
