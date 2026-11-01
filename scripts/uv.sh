#!/usr/bin/env bash
# Run uv inside WSL. The venv lives in the Linux home: it is much faster than /mnt/c,
# and Windows Smart App Control blocks the native .pyd files of pandas/scipy/matplotlib.
# Usage from PowerShell:  wsl bash scripts/uv.sh run python -m pytest
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/senate-forecast-2026"
export UV_LINK_MODE=copy
cd "$(dirname "$0")/.." || exit 1
exec "$HOME/.local/bin/uv" "$@"
