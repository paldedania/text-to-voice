#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This command is for the Linux systemd service." >&2
  exit 1
fi

systemctl --user stop text-to-voice.service
echo "Text to Voice has stopped."
