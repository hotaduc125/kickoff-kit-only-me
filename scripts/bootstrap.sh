#!/bin/sh
# avflow bootstrap (macOS / Linux): installs uv if needed, installs avflow, runs setup.
# Usage: ./bootstrap.sh <wheel file | package spec>   e.g. ./bootstrap.sh avflow-1.0.0-py3-none-any.whl
set -e
SRC="${1:-avflow}"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv…"
  if command -v brew >/dev/null 2>&1; then brew install uv; else curl -LsSf https://astral.sh/uv/install.sh | sh; fi
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
"$UV" tool install --force "$SRC"
"$UV" tool update-shell >/dev/null 2>&1 || true
exec "$HOME/.local/bin/avflow" setup
