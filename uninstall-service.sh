#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This uninstaller is for Linux. Use the matching uninstaller listed in README.md." >&2
  exit 1
fi

unit_name="text-to-voice.service"
config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
unit_path="$config_home/systemd/user/$unit_name"

systemctl --user disable --now "$unit_name" 2>/dev/null || true
if [[ -f "$unit_path" ]]; then
  rm -f -- "$unit_path"
fi
systemctl --user daemon-reload
systemctl --user reset-failed "$unit_name" 2>/dev/null || true

echo "Text to Voice autostart was removed. Local models, settings, and audio were kept."
