#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

api_port="${API_PORT:-8000}"
host="${HOST:-127.0.0.1}"
frontend_origin="${FRONTEND_ORIGIN:-https://fitz135.github.io}"
frontend_url="${FRONTEND_URL:-https://fitz135.github.io/lerobot-data-viewer/}"
api_public_url="${API_PUBLIC_URL:-}"

if [[ -z "${api_public_url}" && -n "${VSCODE_PROXY_URI:-}" ]]; then
  api_public_url="$(
    API_PORT="${api_port}" VSCODE_PROXY_URI="${VSCODE_PROXY_URI}" python - <<'PY'
import os

port = os.environ["API_PORT"]
template = os.environ["VSCODE_PROXY_URI"]
url = (
    template
    .replace("{{port}}", port)
    .replace("{port}", port)
    .replace("%PORT%", port)
)
print(url.rstrip("/"))
PY
  )"
fi

export LDRV_CORS_ORIGINS="${LDRV_CORS_ORIGINS:-${frontend_origin}}"

echo "LeRobot Data Viewer backend"
echo "  bind: ${host}:${api_port}"
echo "  cors: ${LDRV_CORS_ORIGINS}"

if [[ -n "${api_public_url}" ]]; then
  echo
  echo "Open frontend:"
  echo "  ${frontend_url}?api=${api_public_url}/api"
  echo
  echo "API health check:"
  echo "  ${api_public_url}/api/health"
else
  echo
  echo "No public API URL detected."
  echo "Forward port ${api_port} in VS Code, then open:"
  echo "  ${frontend_url}?api=<VSCODE_8000_PROXY_URL>/api"
  echo
fi

if [[ "${PRINT_ONLY:-0}" == "1" ]]; then
  exit 0
fi

exec make api HOST="${host}" API_PORT="${api_port}"
