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

local_health_url="http://${host}:${api_port}/api/health"
if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "${local_health_url}" >/dev/null 2>&1; then
  echo "Existing healthy backend detected at ${local_health_url}"
  echo "No new server was started."
  exit 0
fi

port_open="$(
  HOST="${host}" API_PORT="${api_port}" python - <<'PY' 2>/dev/null || true
import os
import socket

host = os.environ["HOST"]
port = int(os.environ["API_PORT"])
sock = socket.socket()
sock.settimeout(0.5)
try:
    print("open" if sock.connect_ex((host, port)) == 0 else "free")
finally:
    sock.close()
PY
)"

if [[ "${port_open}" == "open" ]]; then
  echo "Port ${host}:${api_port} is already in use, but it is not a healthy LeRobot Data Viewer API."
  echo "Stop the existing process or start this backend on another port:"
  echo "  API_PORT=8001 ./scripts/start_server.sh"
  echo
  echo "If you use another port, forward that port in VS Code and use its proxy URL."
  exit 1
fi

exec make api HOST="${host}" API_PORT="${api_port}"
