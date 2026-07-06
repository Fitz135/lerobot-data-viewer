# Public Frontend Deployment

The frontend can be deployed as a static site, including GitHub Pages. The
backend cannot be replaced by GitHub Pages because it reads SQLite, parquet
files, and mp4 videos from the server.

## Required Pieces

1. A static frontend URL, for example `https://USER.github.io/REPO/`.
2. A public HTTPS backend URL, for example `https://viewer-api.example.com/api`.
3. Backend CORS configured to allow the frontend origin.

GitHub Pages is HTTPS. For a public deployment, use an HTTPS backend URL to
avoid browser mixed-content blocking.

The production frontend also has runtime API configuration. Users can set the
API base in the top-right `Set API` field, or pass it in the URL:

```text
https://fitz135.github.io/lerobot-data-viewer/?api=https://viewer-api.example.com/api
```

## Build Frontend For GitHub Pages

If the repo is served from `https://USER.github.io/REPO/`, build with:

```bash
make frontend-build-public \
  PUBLIC_API_BASE=https://viewer-api.example.com/api \
  PUBLIC_BASE_PATH=/REPO/
```

Then publish `web/dist/` to GitHub Pages.

For a user or organization site served from `https://USER.github.io/`, use:

```bash
make frontend-build-public \
  PUBLIC_API_BASE=https://viewer-api.example.com/api \
  PUBLIC_BASE_PATH=/
```

## Start Backend For Public Frontend

Run the backend with CORS allowing your GitHub Pages origin:

```bash
LDRV_CORS_ORIGINS=https://USER.github.io make api
```

If your site is a project page, the origin is still only
`https://USER.github.io`; paths such as `/REPO/` are not part of the CORS
origin.

## VS Code Proxy Backend

On a headless server where only VS Code forwarded ports are exposed, use:

```bash
./scripts/start_server.sh
```

The script:

- starts the FastAPI backend on `127.0.0.1:8000`
- sets `LDRV_CORS_ORIGINS=https://fitz135.github.io` by default
- derives the public backend URL from `VSCODE_PROXY_URI` when available
- prints the GitHub Pages URL with `api=<proxy-url>/api`
- reuses an already healthy backend on the same port

If `VSCODE_PROXY_URI` is not available in the shell, forward port `8000` in the
VS Code Ports panel and use the forwarded URL manually:

```text
https://fitz135.github.io/lerobot-data-viewer/?api=<VSCODE_8000_PROXY_URL>/api
```

If port `8000` is occupied by another process:

```bash
API_PORT=8001 ./scripts/start_server.sh
```

## Backend Exposure Options

Recommended options:

- Put FastAPI behind Nginx or Caddy with HTTPS and basic auth, VPN, or IP
  allowlist.
- Use Cloudflare Tunnel, Tailscale Funnel, or a similar HTTPS tunnel for
  private testing.

Avoid binding the API directly to `0.0.0.0` without authentication. The media
endpoint streams registered dataset videos and should not be public unless the
data is intended to be public.
