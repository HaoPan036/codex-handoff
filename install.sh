#!/usr/bin/env bash
set -euo pipefail
THRESHOLD="${1:-3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/scripts/install_profile.py" --threshold "$THRESHOLD"
