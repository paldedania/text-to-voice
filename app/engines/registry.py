from __future__ import annotations

from app.engines.base import SpeechEngine
from app.engines.chatterbox import ChatterboxEngine
from app.engines.diagnostic import DiagnosticEngine
from app.engines.kokoro import KokoroEngine


class EngineRegistry:
    def __init__(self) -> None:
        engines: tuple[SpeechEngine, ...] = (
            ChatterboxEngine("multilingual"),
            ChatterboxEngine("turbo"),
            KokoroEngine(),
            DiagnosticEngine(),
        )
        self._engines = {engine.info.id: engine for engine in engines}

    def all(self) -> list[SpeechEngine]:
        return list(self._engines.values())

    def get(self, engine_id: str) -> SpeechEngine:
        try:
            return self._engines[engine_id]
        except KeyError as error:
            raise ValueError(f"Unknown speech engine '{engine_id}'.") from error
