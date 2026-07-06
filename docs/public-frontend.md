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

## Backend Exposure Options

Recommended options:

- Put FastAPI behind Nginx or Caddy with HTTPS and basic auth, VPN, or IP
  allowlist.
- Use Cloudflare Tunnel, Tailscale Funnel, or a similar HTTPS tunnel for
  private testing.

Avoid binding the API directly to `0.0.0.0` without authentication. The media
endpoint streams registered dataset videos and should not be public unless the
data is intended to be public.

