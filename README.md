# LeRobot Data Viewer

Local read-only dashboard and episode browser for LeRobot v2.1 datasets.

## Features

- Global, dataset, task, and episode-level dashboard views.
- Explicit dataset registry in `config/datasets.yaml`.
- SQLite-backed index cache with generation-based refresh safety.
- Dataset-level episode lookup by episode id.
- Episode browser with synchronized videos, timeline, and uPlot state/action curves.
- Read-only health checks for metadata, parquet, video, and numeric series.
- Public static frontend on GitHub Pages with runtime API URL configuration.

## Quick Start

```bash
make install
make index-smoke
make dev
```

Open the web app at `http://127.0.0.1:5173`.

The public frontend is available at:

```text
https://fitz135.github.io/lerobot-data-viewer/
```

For the public frontend, set the API URL in the top-right `Set API` field, or
open it with:

```text
https://fitz135.github.io/lerobot-data-viewer/?api=<PUBLIC_BACKEND_URL>/api
```

## Common Commands

```bash
make api          # Start FastAPI on 127.0.0.1:8000
make web          # Start Vite on 127.0.0.1:5173
make dev          # Start both servers
make index-smoke  # Index a small subset for quick validation
make index        # Deep-index all registered data
make test         # Backend tests and frontend build
```

## Documentation

- [Design plan](docs/plan.md)
- [Public frontend deployment](docs/public-frontend.md)
- [Changelog](docs/changelog.md)

## Episode Lookup

Open a dataset detail page and use `Find Episode`.

Accepted query forms:

```text
12
episode_000012
episode_000012.parquet
task_id/12
task_id/episode_000012
dataset_id/task_id/12
```

Only entering an episode index searches the current dataset across all tasks.
Including a task id narrows the result to one task.

## VS Code Proxy Startup

For a headless server where only VS Code forwarded ports are exposed:

```bash
./scripts/start_server.sh
```

If `VSCODE_PROXY_URI` is available, the script prints the full GitHub Pages URL
with the `api=` parameter already filled in. Otherwise forward port `8000` in
the VS Code Ports panel and use the printed URL template.

To verify the printed URLs without starting the backend:

```bash
PRINT_ONLY=1 ./scripts/start_server.sh
```

If port `8000` is already used by another process:

```bash
API_PORT=8001 ./scripts/start_server.sh
```

If a backend is already running on the selected port and responds to
`/api/health`, the script reuses it and does not start a duplicate server.

The first version is read-only. It writes only local cache/index data under
`backend/data/` and never modifies the LeRobot dataset roots.
