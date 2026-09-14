# Text to Voice

Text to Voice is a private speech-generation studio that runs on `127.0.0.1`. The browser sends text only to the Python process on this computer. Chatterbox and Kokoro adapters are included, but their packages and weights remain optional.

## Current state

| Part | Status |
|---|---|
| Local browser interface | Implemented |
| One-job generation queue | Implemented |
| WAV, MP3 and Opus output | Implemented |
| SQLite history | Implemented |
| Reference recording upload | Implemented with consent and size checks |
| Diagnostic audio engine | Implemented |
| Kokoro adapter | Implemented, package not installed by default |
| English-to-language translation | Implemented with local M2M100 418M |
| Chatterbox Multilingual V3 adapter | Implemented; upstream package is not installed in this environment |
| Chatterbox Turbo adapter | Implemented; upstream package is not installed in this environment |
| Chatterbox speed control | Implemented through local FFmpeg pitch-preserving processing |
| Strict offline operation | Supported after packages and weights are cached |

## Install the application shell

The project uses Python 3.11 because Chatterbox documents and tests that version.

```bash
cd /home/pal/Workspace/projects/text-to-voice
uv sync --extra dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The built-in diagnostic engine tests the interface, queue, database, audio conversion and player. It produces tones, not speech.

After the environment is installed, the shorter launch command is:

```bash
./run.sh
```

`run.sh` keeps the server attached to that terminal. For normal use, install the permanent user service once:

```bash
./install-service.sh
```

The installer reads the current clone location, writes the service to the user's systemd configuration, starts it immediately, and enables it for future logins. It works when the repository is cloned to a different directory. Re-run the installer if the repository is moved later.

Check, stop, or start the service with:

```bash
systemctl --user status text-to-voice.service
./stop-background.sh
./start-background.sh
```

The service survives terminal closure, restarts after an application crash, and starts automatically after reboot when the user logs in. Remove only the autostart configuration with:

```bash
./uninstall-service.sh
```

Uninstalling the service keeps downloaded models, settings, job history, and generated audio.

## Check the RTX 5050

```bash
uv run python scripts/check_gpu.py
```

GPU mode is ready only when both checks pass:

```text
nvidia-smi returns the RTX 5050 and its memory
torch.cuda.is_available() returns true
```

On this machine the driver reports an NVIDIA GeForce RTX 5050 Laptop GPU with 8,151 MiB of usable VRAM. PyTorch still needs to be installed with one of the speech-model extras before `torch.cuda.is_available()` can be checked.

## Add Kokoro

Kokoro is the recommended first speech model because it is small and its preset voices work on CPU or GPU.

```bash
uv sync --extra dev --extra kokoro
```

Kokoro also needs `espeak-ng` for several language paths. Install it with the operating system package manager, then start the application again. The first generation downloads the public Kokoro weights and selected voice into the local Hugging Face cache.

Selecting Hindi, Spanish, French, Italian, Portuguese, Japanese or Chinese translates the English script locally before Kokoro creates speech. The first translated job downloads `facebook/m2m100_418M`, including its roughly 1.94 GB model weight file. English and British English skip translation. The Output section shows the translated script for review.

Run a direct English benchmark:

```bash
uv run python scripts/benchmark.py kokoro --voice af_heart --language en
```

Run a Hindi benchmark:

```bash
uv run python scripts/benchmark.py kokoro --voice hf_alpha --language hi
```

## Chatterbox compatibility note

The Chatterbox adapters are ready, but the current upstream Python 3.11 package pins PyTorch 2.6/CUDA 12.4. That wheel cannot execute on this RTX 5050 (`sm_120`). The application therefore does not expose a misleading `chatterbox` install extra. Keep Kokoro as the working engine until Chatterbox supports PyTorch 2.7+ with CUDA 12.8 or newer, or run Chatterbox in a separately tested environment.

When a compatible package is available, Chatterbox Multilingual V3 can use the saved reference recordings already supported by the Voice lab. Aim for 6–15 seconds with no music, echo, or overlapping speech. Chatterbox embeds an imperceptible Perth watermark in generated audio.

## Run without a network after setup

Download the selected model and voice once. Then start the app with the model hubs disabled:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Keep the host set to `127.0.0.1`. Binding to `0.0.0.0` makes the application reachable from the local network and needs authentication that this version does not implement.

## Test

```bash
uv run pytest
uv run ruff check .
```

The API test generates a real WAV file using the diagnostic engine. It does not need CUDA or model weights.

## Local data

| Path | Contents |
|---|---|
| `data/text-to-voice.sqlite3` | Job history and saved voice metadata |
| `data/output/` | Generated audio |
| `data/voices/` | Permitted reference recordings |

These paths are excluded from Git. Delete them to remove the local application history and audio. Stop the application before deleting its database.

## Local endpoints

| Route | Purpose |
|---|---|
| `GET /api/system` | GPU, PyTorch and FFmpeg status |
| `GET /api/engines` | Installed and missing speech engines |
| `POST /api/synthesize` | Queue a speech job |
| `GET /api/jobs/{id}` | Read generation progress |
| `GET /api/audio/{id}` | Play or download completed audio |
| `GET /api/history` | Read recent local jobs |
| `POST /api/voices` | Save a permitted reference recording |
