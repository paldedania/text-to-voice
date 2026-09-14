from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from app.engines.base import GenerationInput  # noqa: E402
from app.engines.registry import EngineRegistry  # noqa: E402

TEST_TEXT = (
    "This is a local speech benchmark. It includes the number 2026, the abbreviation GPU, "
    "and enough punctuation to test rhythm, timing, and pronunciation."
)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark one installed local speech engine.")
    parser.add_argument(
        "engine", choices=["diagnostic", "kokoro", "chatterbox-turbo", "chatterbox-multilingual"]
    )
    parser.add_argument("--voice", default="signal")
    parser.add_argument("--language", default="en")
    parser.add_argument("--text", default=TEST_TEXT)
    parser.add_argument(
        "--output", type=Path, default=PROJECT_DIR / "data" / "output" / "benchmark.wav"
    )
    arguments = parser.parse_args()

    engine = EngineRegistry().get(arguments.engine)
    if not engine.info.available:
        print(engine.info.availability_note, file=sys.stderr)
        return 2

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    engine.synthesize(
        GenerationInput(
            text=arguments.text,
            voice_id=arguments.voice,
            language=arguments.language,
            speed=1.0,
        ),
        arguments.output,
        lambda progress: print(f"\rProgress: {progress:3d}%", end="", flush=True),
    )
    elapsed = time.perf_counter() - started
    duration = wav_duration(arguments.output)
    print(f"\nOutput: {arguments.output}")
    print(f"Generation: {elapsed:.3f} seconds")
    print(f"Audio: {duration:.3f} seconds")
    print(f"Real-time factor: {elapsed / duration:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
