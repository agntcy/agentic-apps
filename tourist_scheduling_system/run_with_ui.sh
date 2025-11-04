#!/usr/bin/env bash
# Wrapper around uv-based launcher. Ensures we run from project root.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec bash "$SCRIPT_DIR/scripts/run_with_ui.sh" "$@"
