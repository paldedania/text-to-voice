from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ProgressCallback = Callable[[int], None]


@dataclass(frozen=True, slots=True)
class Voice:
    id: str
    name: str
    language: str


@dataclass(frozen=True, slots=True)
class EngineInfo:
    id: str
    name: str
    description: str
    available: bool
    availability_note: str
    supports_cloning: bool
    supports_streaming: bool
    languages: tuple[str, ...]
    voices: tuple[Voice, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class GenerationInput:
    text: str
    voice_id: str
    language: str
    speed: float
    reference_audio: Path | None = None


class SpeechEngine(ABC):
    @property
    @abstractmethod
    def info(self) -> EngineInfo:
        raise NotImplementedError

    @abstractmethod
    def synthesize(
        self,
        request: GenerationInput,
        output_path: Path,
        progress: ProgressCallback,
    ) -> None:
        """Write mono WAV audio to output_path."""
        raise NotImplementedError
