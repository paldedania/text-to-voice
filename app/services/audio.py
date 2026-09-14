from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def adjust_wav_speed(source: Path, speed: float) -> None:
    """Change playback speed without changing pitch, in place."""
    if abs(speed - 1.0) < 0.001:
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for Chatterbox speed control.")

    adjusted = source.with_suffix(".speed.wav")
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-filter:a",
            f"atempo={speed:.4f}",
            str(adjusted),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        adjusted.unlink(missing_ok=True)
        message = result.stderr.strip() or "FFmpeg could not adjust the audio speed."
        raise RuntimeError(message)
    adjusted.replace(source)


def convert_wav(source: Path, destination: Path, output_format: str) -> None:
    if output_format == "wav":
        source.replace(destination)
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for MP3 and Opus export.")

    codec_arguments = {
        "mp3": ["-codec:a", "libmp3lame", "-b:a", "128k"],
        "opus": ["-codec:a", "libopus", "-b:a", "64k"],
    }
    if output_format not in codec_arguments:
        raise ValueError(f"Unsupported output format '{output_format}'.")

    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            *codec_arguments[output_format],
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "FFmpeg could not convert the generated audio."
        raise RuntimeError(message)
    source.unlink(missing_ok=True)
