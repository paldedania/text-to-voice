# Text to Voice

A local-first multilingual text-to-speech web app. Kokoro creates speech, and M2M100 translates English before non-English synthesis. No API key or cloud speech service is required.

## What it supports

| System | Run locally | Start at sign-in | Acceleration |
|---|---|---|---|
| Windows 10/11 x64 | `run.ps1` | Task Scheduler script | NVIDIA CUDA or CPU |
| macOS 13+ (Apple Silicon) | `run.sh` | LaunchAgent script | CPU |
| Modern Linux x64 | `run.sh` | systemd user service | NVIDIA CUDA or CPU |

The normal app and automated tests are cross-platform. The startup scripts use each operating system's native service manager; they are not one Linux-only solution.

Windows on ARM, Intel Macs, and Linux ARM are not supported by the current locked speech-model stack.

## Requirements

| Resource | Minimum | Recommended |
|---|---:|---:|
| Python | 3.11 | 3.11 |
| Memory | 8 GB RAM | 16 GB RAM |
| Free disk | 12 GB | 15 GB |
| GPU | None | NVIDIA GPU with 8 GB+ VRAM |

Install [uv](https://docs.astral.sh/uv/), [FFmpeg](https://ffmpeg.org/download.html), and [eSpeak NG](https://github.com/espeak-ng/espeak-ng/releases). Internet is needed for setup and the first model download; later use is local.

## Install and run

```text
git clone https://github.com/paldedania/text-to-voice.git
cd text-to-voice
uv sync --extra dev --extra kokoro --extra cpu
```

Then run `./run.sh` on macOS/Linux or `.\run.ps1` in Windows PowerShell. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

The command above works everywhere. On Windows or Linux with an NVIDIA GPU, replace `--extra cpu` with `--extra cuda`. Do not select both.

The first translated job downloads M2M100 (about 1.9 GB). Kokoro models and voices are also cached locally.

## Optional start at sign-in

| System | Install | Remove |
|---|---|---|
| Windows PowerShell | `.\install-service-windows.ps1` | `.\uninstall-service-windows.ps1` |
| macOS Terminal | `./install-service-macos.sh` | `./uninstall-service-macos.sh` |
| Linux Terminal | `./install-service.sh` | `./uninstall-service.sh` |

Run the matching installer after `uv sync`. It records the current clone location, so rerun it if you move the repository.

## Language behavior

English and British English are spoken as written. Selecting Hindi, Spanish, French, Italian, Portuguese, Japanese, or Chinese translates the English text locally and then uses a matching voice. Review important translations before using the audio.

## Hardware check and tests

```bash
uv run python scripts/check_gpu.py
uv run pytest
uv run ruff check .
```

CUDA is used when a compatible NVIDIA GPU is available; otherwise the app uses CPU. GitHub Actions runs the core test suite on Windows, macOS, and Linux. GPU inference is tested on real hardware, not hosted CI.

## Privacy

Generated audio, job history, and reference recordings stay under `data/` and are ignored by Git. The server only listens on `127.0.0.1`; add authentication before exposing it to a network.
