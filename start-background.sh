#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
unit_name="text-to-voice.service"

if ! systemctl --user cat "$unit_name" >/dev/null 2>&1; then
  echo "The permanent user service is not installed. Run: $project_dir/install-service.sh" >&2
  exit 1
fi

systemctl --user enable --now "$unit_name"

for attempt in {1..10}; do
  if curl --fail --silent http://127.0.0.1:8765/api/system >/dev/null; then
    echo "Text to Voice is running at http://127.0.0.1:8765/"
    exit 0
  fi
  sleep 1
done

echo "The service started but did not answer within 10 seconds." >&2
systemctl --user status "$unit_name" --no-pager >&2
exit 1
