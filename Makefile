SHELL := /bin/bash

HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 5173
DATASET ?= rdt_lerobot_v21
UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
NPM_CONFIG_CACHE ?= $(CURDIR)/.npm-cache
PUBLIC_API_BASE ?=
PUBLIC_BASE_PATH ?= /

.PHONY: install api web dev index index-smoke test backend-test frontend-build frontend-build-public

install:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --extra test
	cd web && npm_config_cache=$(NPM_CONFIG_CACHE) npm install

api:
	UV_CACHE_DIR=$(UV_CACHE_DIR) LDRV_HOST=$(HOST) LDRV_PORT=$(API_PORT) uv run uvicorn lerobot_viewer.main:app --app-dir backend --host $(HOST) --port $(API_PORT) --reload

web:
	cd web && npm_config_cache=$(NPM_CONFIG_CACHE) npm run dev -- --host $(HOST) --port $(WEB_PORT)

dev:
	$(MAKE) -j2 api web

index:
	UV_CACHE_DIR=$(UV_CACHE_DIR) PYTHONPATH=backend uv run python -m lerobot_viewer.cli index --dataset $(DATASET) --deep

index-smoke:
	UV_CACHE_DIR=$(UV_CACHE_DIR) PYTHONPATH=backend uv run python -m lerobot_viewer.cli index --dataset $(DATASET) --deep --smoke --max-tasks 2 --max-episodes-per-task 2

backend-test:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest

frontend-build:
	cd web && npm_config_cache=$(NPM_CONFIG_CACHE) npm run build

frontend-build-public:
	cd web && npm_config_cache=$(NPM_CONFIG_CACHE) VITE_API_BASE=$(PUBLIC_API_BASE) VITE_BASE_PATH=$(PUBLIC_BASE_PATH) npm run build

test: backend-test frontend-build
