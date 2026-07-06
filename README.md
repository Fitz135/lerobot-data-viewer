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

The first version is read-only. It writes only local cache/index data under
`backend/data/` and never modifies the LeRobot dataset roots.
