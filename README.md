# Text to Voice

A local-first web app for multilingual text-to-speech. It uses Kokoro for speech and M2M100 to translate English text before synthesis. No provider API key is required.

## Features

- Local speech generation with language-matched Kokoro voices
- English translation into Hindi, Spanish, French, Italian, Portuguese, Japanese and Chinese
- WAV, MP3 and Opus output
- SQLite job history and a one-job generation queue
- Optional reference recordings for compatible voice-cloning engines
- CPU and NVIDIA CUDA support

## Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- FFmpeg
- `espeak-ng`
- An NVIDIA GPU is optional

Internet access is required during installation and the first model download.

## Quick start

```bash
git clone https://github.com/paldedania/text-to-voice.git
cd text-to-voice
uv sync --extra dev --extra kokoro
./run.sh
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

The first translated job downloads the M2M100 model, which is about 1.9 GB. Kokoro weights and selected voices are also cached locally. Later runs can work without a network connection.

## Background service on Linux

Install the user service once to start the app automatically at login:

```bash
./install-service.sh
```

The installer uses the current clone location, so the repository can be stored anywhere. Re-run it after moving the project.

```bash
./start-background.sh     # start
./stop-background.sh      # stop
./uninstall-service.sh    # remove autostart, keep local data
```

## How language selection works

English and British English are spoken as written. Selecting another language first translates the English script locally, then sends the translated text to the matching Kokoro voice. The translated script appears in the output for review.

Machine translation can make mistakes. Review important scripts before using the audio.

## GPU check

```bash
uv run python scripts/check_gpu.py
```

The app uses CUDA when PyTorch detects a compatible NVIDIA GPU and falls back to CPU otherwise.

## Tests

```bash
uv run pytest
uv run ruff check .
```

## Local data and privacy

Job history, generated audio and reference recordings are stored under `data/`. Git ignores those files, downloaded models, virtual environments and environment files.

The server binds to `127.0.0.1` and has no public authentication. Do not bind it to `0.0.0.0` or expose it to the internet without adding authentication and rate limits.

## Chatterbox

Chatterbox adapters are included, but Chatterbox is not part of the supported install because its current dependency stack is incompatible with some recent NVIDIA GPU environments. Kokoro is the supported speech engine in this release.
