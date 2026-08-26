#!/usr/bin/env bash
# Installs a launchd agent that runs discovery daily at 08:00.
# The plist is generated at install time — no hardcoded home paths.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$REPO_DIR/.venv/bin/python"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/com.sprayandpray.discovery.plist"
LABEL="com.sprayandpray.discovery"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "No virtualenv found at $PYTHON_BIN" >&2
    echo "Create one first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$REPO_DIR/cv_optimizer.py</string>
        <string>discover</string>
    </array>

    <!-- Daily at 08:00. To move to every 6 hours, replace the two keys
         below with StartInterval = 21600 (and delete StartCalendarInterval). -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>

    <key>StandardOutPath</key>
    <string>$REPO_DIR/.discovery.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/.discovery.launchd.log</string>

    <key>RunAtLoad</key>
    <false/>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Installed $PLIST_PATH"
echo "Discovery will run daily at 08:00."
echo "  Current schedule: launchctl print gui/\$(id -u)/$LABEL | grep -A3 StartCalendarInterval"
echo "  Uninstall:        scripts/uninstall_discovery_launchd.sh"
