#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$project_dir"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "The project environment is missing. Follow the setup command in README.md." >&2
  exit 1
fi

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765
