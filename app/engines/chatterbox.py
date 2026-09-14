from __future__ import annotations

import importlib.util
from pathlib import Path

from app.engines.base import EngineInfo, GenerationInput, ProgressCallback, SpeechEngine, Voice
from app.services.text import split_text

CHATTERBOX_LANGUAGES = (
    "ar",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fi",
    "fr",
    "he",
    "hi",
    "it",
    "ja",
    "ko",
    "ms",
    "nl",
    "no",
    "pl",
    "pt",
    "ru",
    "sv",
    "sw",
    "tr",
    "zh",
)


class ChatterboxEngine(SpeechEngine):
    def __init__(self, variant: str = "multilingual") -> None:
        if variant not in {"multilingual", "turbo"}:
            raise ValueError("Unsupported Chatterbox variant")
        self.variant = variant
        self._model = None

    @property
    def info(self) -> EngineInfo:
        installed = importlib.util.find_spec("chatterbox") is not None
        multilingual = self.variant == "multilingual"
        return EngineInfo(
            id=f"chatterbox-{self.variant}",
            name="Chatterbox Multilingual V3" if multilingual else "Chatterbox Turbo",
            description=(
                "Quality mode with multilingual voice cloning."
                if multilingual
                else "Fast English speech with voice cloning and expression tags."
            ),
            available=installed,
            availability_note=(
                "Ready" if installed else "Install Chatterbox and CUDA-compatible PyTorch"
            ),
            supports_cloning=True,
            supports_streaming=False,
            languages=CHATTERBOX_LANGUAGES if multilingual else ("en",),
            voices=(Voice("default", "Built-in voice", "multi" if multilingual else "en"),),
        )

    def _load(self):
        if self._model is not None:
            return self._model
        if not self.info.available:
            raise RuntimeError("Chatterbox is not installed.")

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.variant == "multilingual":
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            self._model = ChatterboxMultilingualTTS.from_pretrained(
                device=device,
                t3_model="v3",
            )
        else:
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            self._model = ChatterboxTurboTTS.from_pretrained(device=device)
        return self._model

    def synthesize(
        self,
        request: GenerationInput,
        output_path: Path,
        progress: ProgressCallback,
    ) -> None:
        import torch
        import torchaudio

        model = self._load()
        chunks = split_text(request.text, max_characters=650)
        if not chunks:
            raise ValueError("The normalized text is empty.")

        audio_parts = []
        silence = torch.zeros(1, int(model.sr * 0.16))
        for index, chunk in enumerate(chunks):
            arguments = {}
            if request.reference_audio:
                arguments["audio_prompt_path"] = str(request.reference_audio)
            if self.variant == "multilingual":
                arguments["language_id"] = request.language
            audio = model.generate(chunk, **arguments)
            if audio.dim() == 1:
                audio = audio.unsqueeze(0)
            if audio_parts:
                audio_parts.append(silence.to(audio.device))
            audio_parts.append(audio)
            progress(round((index + 1) / len(chunks) * 100))

        combined = torch.cat([part.cpu() for part in audio_parts], dim=-1)
        torchaudio.save(str(output_path), combined, model.sr)
