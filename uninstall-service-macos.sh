#!/usr/bin/env bash
set -euo pipefail

label="io.github.paldedania.text-to-voice"
agent_path="${HOME}/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"

launchctl bootout "$domain" "$agent_path" >/dev/null 2>&1 || true
if [[ -f "$agent_path" ]]; then
  rm -f -- "$agent_path"
fi

echo "Text to Voice autostart was removed. Local models, settings, and audio were kept."
