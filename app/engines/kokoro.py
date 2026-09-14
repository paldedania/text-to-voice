from __future__ import annotations

import importlib.util
from pathlib import Path

from app.engines.base import EngineInfo, GenerationInput, ProgressCallback, SpeechEngine, Voice
from app.services.text import split_text

LANGUAGE_CODES = {
    "en": "a",
    "en-gb": "b",
    "hi": "h",
    "es": "e",
    "fr": "f",
    "it": "i",
    "pt-br": "p",
    "ja": "j",
    "zh": "z",
}

KOKORO_VOICES = (
    Voice("af_heart", "Heart, American English", "en"),
    Voice("af_bella", "Bella, American English", "en"),
    Voice("am_michael", "Michael, American English", "en"),
    Voice("bf_emma", "Emma, British English", "en-gb"),
    Voice("bm_george", "George, British English", "en-gb"),
    Voice("hf_alpha", "Alpha, Hindi", "hi"),
    Voice("hf_beta", "Beta, Hindi", "hi"),
    Voice("hm_omega", "Omega, Hindi", "hi"),
    Voice("hm_psi", "Psi, Hindi", "hi"),
    Voice("ef_dora", "Dora, Spanish", "es"),
    Voice("em_alex", "Alex, Spanish", "es"),
    Voice("ff_siwis", "Siwis, French", "fr"),
    Voice("if_sara", "Sara, Italian", "it"),
    Voice("im_nicola", "Nicola, Italian", "it"),
    Voice("pf_dora", "Dora, Brazilian Portuguese", "pt-br"),
    Voice("pm_alex", "Alex, Brazilian Portuguese", "pt-br"),
    Voice("jf_alpha", "Alpha, Japanese", "ja"),
    Voice("jm_kumo", "Kumo, Japanese", "ja"),
    Voice("zf_xiaobei", "Xiaobei, Mandarin Chinese", "zh"),
    Voice("zm_yunjian", "Yunjian, Mandarin Chinese", "zh"),
)


class KokoroEngine(SpeechEngine):
    def __init__(self) -> None:
        self._pipelines: dict[str, object] = {}

    @property
    def info(self) -> EngineInfo:
        installed = importlib.util.find_spec("kokoro") is not None
        return EngineInfo(
            id="kokoro",
            name="Kokoro 82M",
            description="Fast preset voices for everyday reading.",
            available=installed,
            availability_note=(
                "Ready" if installed else "Install the local Kokoro package and espeak-ng"
            ),
            supports_cloning=False,
            supports_streaming=False,
            languages=tuple(LANGUAGE_CODES),
            voices=KOKORO_VOICES,
        )

    def _pipeline(self, language: str):
        language_code = LANGUAGE_CODES.get(language)
        if language_code is None:
            raise ValueError(f"Kokoro does not support language '{language}' in this app.")
        if language_code not in self._pipelines:
            from kokoro import KPipeline

            self._pipelines[language_code] = KPipeline(lang_code=language_code)
        return self._pipelines[language_code]

    def synthesize(
        self,
        request: GenerationInput,
        output_path: Path,
        progress: ProgressCallback,
    ) -> None:
        if not self.info.available:
            raise RuntimeError("Kokoro is not installed.")

        import numpy as np
        import soundfile as sf

        chunks = split_text(request.text, max_characters=500)
        if not chunks:
            raise ValueError("The normalized text is empty.")

        pipeline = self._pipeline(request.language)
        audio_parts = []
        silence = np.zeros(int(24_000 * 0.16), dtype=np.float32)
        for index, chunk in enumerate(chunks):
            generated = pipeline(
                chunk,
                voice=request.voice_id,
                speed=request.speed,
                split_pattern=r"\n+",
            )
            chunk_parts = [audio for _graphemes, _phonemes, audio in generated]
            if chunk_parts:
                if audio_parts:
                    audio_parts.append(silence)
                audio_parts.extend(chunk_parts)
            progress(round((index + 1) / len(chunks) * 100))

        if not audio_parts:
            raise RuntimeError("Kokoro returned no audio.")
        sf.write(output_path, np.concatenate(audio_parts), 24_000, subtype="PCM_16")
