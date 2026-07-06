# LeRobot Data Viewer

Local read-only dashboard and episode browser for LeRobot v2.1 datasets.

## Quick Start

```bash
make install
make index-smoke
make dev
```

Open the web app at `http://127.0.0.1:5173`.

## Common Commands

```bash
make api          # Start FastAPI on 127.0.0.1:8000
make web          # Start Vite on 127.0.0.1:5173
make dev          # Start both servers
make index-smoke  # Index a small subset for quick validation
make index        # Deep-index all registered data
make test         # Backend tests and frontend build
```

The first version is read-only. It writes only local cache/index data under
`backend/data/` and never modifies the LeRobot dataset roots.

