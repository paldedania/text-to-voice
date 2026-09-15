from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.text import has_visible_text

AudioFormat = Literal["wav", "mp3", "opus"]


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    engine: str = Field(min_length=1, max_length=80)
    voice_id: str = Field(default="default", min_length=1, max_length=120)
    language: str = Field(default="en", min_length=2, max_length=12)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    output_format: AudioFormat = "wav"

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not has_visible_text(value):
            raise ValueError("Enter text before generating speech.")
        return value


class JobResponse(BaseModel):
    id: str
    status: str
    progress: int
    engine: str
    voice_id: str
    language: str
    output_format: str
    translated_text: str | None = None
    audio_url: str | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None
    generation_seconds: float | None = None


class EngineResponse(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    availability_note: str
    supports_cloning: bool
    supports_streaming: bool
    languages: list[str]
    voices: list[dict[str, str]]


class VoiceResponse(BaseModel):
    id: str
    name: str
    source_filename: str
    created_at: str
