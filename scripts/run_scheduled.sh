#!/bin/bash
# Reconnect Daily Pipeline - Scheduled Runner
# This script is called by the LaunchAgent to run the daily pipeline.

set -e

# Resolve project directory relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON="${RECONNECT_PYTHON:-$(which python3)}"

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Log file with date
LOG_FILE="$LOG_DIR/pipeline-$(date +%Y-%m-%d).log"

# Change to project directory
cd "$PROJECT_DIR"

# Log start time
echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "Pipeline run started at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Note: .env is loaded by Python (pydantic-settings), not here.
# Sourcing .env in bash breaks on multi-line values.

# Run the pipeline
$PYTHON scripts/run_pipeline.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# Log completion
echo "" >> "$LOG_FILE"
echo "Pipeline completed at $(date) with exit code $EXIT_CODE" >> "$LOG_FILE"

# Keep only last 30 days of logs
find "$LOG_DIR" -name "pipeline-*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
