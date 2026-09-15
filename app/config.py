from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    output_dir: Path
    voices_dir: Path
    database_path: Path
    host: str = "127.0.0.1"
    port: int = 8765
    max_text_characters: int = 20_000
    max_reference_bytes: int = 20 * 1024 * 1024
    max_queued_jobs: int = 8

    @classmethod
    def load(cls) -> Settings:
        data_dir = Path(os.environ.get("TEXT_TO_VOICE_DATA_DIR", PROJECT_DIR / "data")).resolve()
        return cls(
            data_dir=data_dir,
            output_dir=data_dir / "output",
            voices_dir=data_dir / "voices",
            database_path=data_dir / "text-to-voice.sqlite3",
            host=os.environ.get("TEXT_TO_VOICE_HOST", "127.0.0.1"),
            port=int(os.environ.get("TEXT_TO_VOICE_PORT", "8765")),
            max_queued_jobs=max(
                0,
                int(os.environ.get("TEXT_TO_VOICE_MAX_QUEUED_JOBS", "8")),
            ),
        )

    def prepare(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
