from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from app.engines.base import EngineInfo, GenerationInput, ProgressCallback, SpeechEngine, Voice


class DiagnosticEngine(SpeechEngine):
    """Generate a short tone pattern to test the application without a TTS model."""

    @property
    def info(self) -> EngineInfo:
        return EngineInfo(
            id="diagnostic",
            name="Diagnostic tones",
            description="Tests the queue, storage and player. It does not speak the text.",
            available=True,
            availability_note="Built into the application",
            supports_cloning=False,
            supports_streaming=False,
            languages=("en",),
            voices=(Voice("signal", "System test signal", "en"),),
        )

    def synthesize(
        self,
        request: GenerationInput,
        output_path: Path,
        progress: ProgressCallback,
    ) -> None:
        sample_rate = 24_000
        duration = min(5.0, max(1.2, len(request.text.split()) * 0.09))
        sample_count = int(sample_rate * duration)
        checksum = sum(request.text.encode("utf-8"))
        base_frequency = 180 + checksum % 140

        progress(10)
        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            frames = bytearray()
            for index in range(sample_count):
                second = index / sample_rate
                pulse = 1.0 if int(second * 4) % 2 == 0 else 0.18
                envelope = min(1.0, second * 18, (duration - second) * 18)
                sample = math.sin(2 * math.pi * base_frequency * second)
                value = int(8_000 * sample * pulse * max(0.0, envelope))
                frames.extend(struct.pack("<h", value))
            output.writeframes(frames)
        progress(100)
