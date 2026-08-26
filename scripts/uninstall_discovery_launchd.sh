#!/usr/bin/env bash
# Removes the discovery launchd agent.
set -euo pipefail

PLIST_PATH="$HOME/Library/LaunchAgents/com.sprayandpray.discovery.plist"

if [[ -f "$PLIST_PATH" ]]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "Removed $PLIST_PATH"
else
    echo "No discovery launchd agent installed."
fi
