import wave
from pathlib import Path

from app.engines.base import GenerationInput
from app.engines.diagnostic import DiagnosticEngine
from app.services.audio import adjust_wav_speed


def test_diagnostic_engine_writes_playable_wav(tmp_path: Path) -> None:
    output = tmp_path / "signal.wav"
    progress: list[int] = []
    DiagnosticEngine().synthesize(
        GenerationInput(
            text="Test the local audio path.",
            voice_id="signal",
            language="en",
            speed=1.0,
        ),
        output,
        progress.append,
    )

    assert output.stat().st_size > 1_000
    assert progress[-1] == 100
    with wave.open(str(output), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 24_000


def test_speed_adjustment_preserves_wav_and_shortens_audio(tmp_path: Path) -> None:
    output = tmp_path / "signal.wav"
    DiagnosticEngine().synthesize(
        GenerationInput(
            text="This sentence creates enough diagnostic audio for a speed comparison.",
            voice_id="signal",
            language="en",
            speed=1.0,
        ),
        output,
        lambda _progress: None,
    )
    with wave.open(str(output), "rb") as audio:
        original_frames = audio.getnframes()

    adjust_wav_speed(output, 1.5)

    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 24_000
        assert audio.getnframes() < original_frames
