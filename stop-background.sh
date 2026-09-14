#!/usr/bin/env bash
set -euo pipefail

systemctl --user stop text-to-voice.service
echo "Text to Voice has stopped."
