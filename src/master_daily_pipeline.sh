#!/usr/bin/env bash
# Compatibility entrypoint; forwards to the new pipeline location.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/pipeline/master_daily_pipeline.sh" "$@"
