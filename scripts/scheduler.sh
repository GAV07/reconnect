#!/bin/bash
# Reconnect Scheduler Management
# Usage: ./scripts/scheduler.sh [install|uninstall|start|stop|status|run|logs]

set -e

# Resolve project directory relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_NAME="com.reconnect.daily-pipeline.plist"
PLIST_TEMPLATE="$PROJECT_DIR/$PLIST_NAME.template"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LOG_DIR="$PROJECT_DIR/logs"

case "$1" in
    install)
        echo "Installing LaunchAgent..."
        if [ ! -f "$PLIST_TEMPLATE" ]; then
            echo "Error: Template not found at $PLIST_TEMPLATE"
            exit 1
        fi
        mkdir -p "$HOME/Library/LaunchAgents"
        # Generate plist from template with actual paths
        sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PLIST_TEMPLATE" > "$PLIST_DST"
        launchctl load "$PLIST_DST"
        echo "Installed and loaded. Pipeline will run daily at 8:00 AM."
        echo "Project directory: $PROJECT_DIR"
        echo "Use './scripts/scheduler.sh status' to verify."
        ;;

    uninstall)
        echo "Uninstalling LaunchAgent..."
        if [ -f "$PLIST_DST" ]; then
            launchctl unload "$PLIST_DST" 2>/dev/null || true
            rm "$PLIST_DST"
            echo "Uninstalled."
        else
            echo "Not installed."
        fi
        ;;

    start)
        echo "Starting LaunchAgent..."
        launchctl load "$PLIST_DST" 2>/dev/null || echo "Already loaded or not installed."
        ;;

    stop)
        echo "Stopping LaunchAgent..."
        launchctl unload "$PLIST_DST" 2>/dev/null || echo "Already stopped or not installed."
        ;;

    status)
        echo "LaunchAgent status:"
        if launchctl list | grep -q "com.reconnect.daily-pipeline"; then
            echo "  State: RUNNING"
            launchctl list com.reconnect.daily-pipeline 2>/dev/null || true
        else
            echo "  State: NOT RUNNING"
        fi
        echo ""
        echo "Installed: $([ -f "$PLIST_DST" ] && echo "Yes" || echo "No")"
        echo ""
        if [ -f "$LOG_DIR/launchd-stdout.log" ]; then
            echo "Last launchd output:"
            tail -5 "$LOG_DIR/launchd-stdout.log" 2>/dev/null || echo "  (no output)"
        fi
        ;;

    run)
        echo "Running pipeline manually..."
        "$PROJECT_DIR/scripts/run_scheduled.sh"
        ;;

    logs)
        LOG_FILE="$LOG_DIR/pipeline-$(date +%Y-%m-%d).log"
        if [ -f "$LOG_FILE" ]; then
            echo "Today's log ($LOG_FILE):"
            echo "========================================"
            cat "$LOG_FILE"
        else
            echo "No log for today. Recent logs:"
            ls -la "$LOG_DIR"/*.log 2>/dev/null | tail -5 || echo "  No logs found."
        fi
        ;;

    *)
        echo "Reconnect Scheduler Management"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  install    Install and start the daily scheduler (runs at 8 AM)"
        echo "  uninstall  Stop and remove the scheduler"
        echo "  start      Start the scheduler (if installed)"
        echo "  stop       Stop the scheduler"
        echo "  status     Show scheduler status and recent output"
        echo "  run        Run the pipeline manually now"
        echo "  logs       Show today's pipeline log"
        echo ""
        echo "Schedule: Daily at 8:00 AM"
        echo "Logs: $LOG_DIR/"
        ;;
esac
