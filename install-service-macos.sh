#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS. Use install-service.sh on Linux." >&2
  exit 1
fi

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
label="io.github.paldedania.text-to-voice"
agent_dir="${HOME}/Library/LaunchAgents"
agent_path="$agent_dir/$label.plist"
log_dir="${HOME}/Library/Logs/TextToVoice"
template_path="$project_dir/launchd/$label.plist.in"
python_path="$project_dir/.venv/bin/python"
uvicorn_path="$project_dir/.venv/bin/uvicorn"
domain="gui/$(id -u)"

if [[ ! -x "$python_path" || ! -x "$uvicorn_path" ]]; then
  echo "The project environment is missing. Follow the setup command in README.md." >&2
  exit 1
fi

mkdir -p "$agent_dir" "$log_dir"
temporary_agent=$(mktemp "$agent_dir/.text-to-voice.XXXXXX")
cleanup() {
  rm -f -- "$temporary_agent"
}
trap cleanup EXIT

"$python_path" "$project_dir/scripts/render_launchd_service.py" \
  "$template_path" "$temporary_agent" "$project_dir" "$log_dir"
chmod 0644 "$temporary_agent"
mv -f -- "$temporary_agent" "$agent_path"
trap - EXIT

launchctl bootout "$domain" "$agent_path" >/dev/null 2>&1 || true
launchctl bootstrap "$domain" "$agent_path"
launchctl enable "$domain/$label"
launchctl kickstart -k "$domain/$label"

echo "Text to Voice is installed and will start when you sign in."
echo "Open http://127.0.0.1:8765/ after the server starts."
