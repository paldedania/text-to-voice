#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer is for Linux. Use the matching installer listed in README.md." >&2
  exit 1
fi

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
unit_name="text-to-voice.service"
config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
unit_dir="$config_home/systemd/user"
unit_path="$unit_dir/$unit_name"
template_path="$project_dir/systemd/text-to-voice.service.in"
python_path="$project_dir/.venv/bin/python"
uvicorn_path="$project_dir/.venv/bin/uvicorn"

if [[ ! -x "$python_path" || ! -x "$uvicorn_path" ]]; then
  echo "The project environment is missing. Follow the setup command in README.md." >&2
  exit 1
fi

mkdir -p "$unit_dir"
temporary_unit=$(mktemp "$unit_dir/.text-to-voice.service.XXXXXX")
cleanup() {
  rm -f -- "$temporary_unit"
}
trap cleanup EXIT

"$python_path" "$project_dir/scripts/render_user_service.py" \
  "$template_path" "$temporary_unit" "$project_dir"
chmod 0644 "$temporary_unit"
mv -f -- "$temporary_unit" "$unit_path"
trap - EXIT

systemctl --user daemon-reload
systemctl --user enable --now "$unit_name"

for attempt in {1..20}; do
  if curl --fail --silent http://127.0.0.1:8765/api/system >/dev/null; then
    echo "Text to Voice is installed and running at http://127.0.0.1:8765/"
    echo "It will start automatically when this user logs in."
    exit 0
  fi
  sleep 1
done

echo "The service was enabled but did not answer within 20 seconds." >&2
systemctl --user status "$unit_name" --no-pager >&2
exit 1
