from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from app.db import Database, utc_now
from app.engines.base import GenerationInput
from app.engines.registry import EngineRegistry
from app.schemas import SynthesisRequest
from app.services.audio import adjust_wav_speed, convert_wav
from app.services.text import normalize_text
from app.services.translation import LocalTranslator


class JobManager:
    def __init__(self, database: Database, registry: EngineRegistry, output_dir: Path) -> None:
        self.database = database
        self.registry = registry
        self.output_dir = output_dir
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts-worker")
        self.translator = LocalTranslator()
        self.futures: dict[str, Future[None]] = {}
        self.lock = threading.Lock()

    def submit(self, request: SynthesisRequest) -> dict:
        engine = self.registry.get(request.engine)
        if not engine.info.available:
            raise RuntimeError(engine.info.availability_note)
        if request.language not in engine.info.languages:
            raise ValueError(f"{engine.info.name} does not support '{request.language}'.")

        text = normalize_text(request.text)
        reference_audio = self._resolve_reference_audio(request.voice_id)
        self._validate_voice(
            engine.info.id,
            request.voice_id,
            request.language,
            reference_audio,
        )

        job_id = uuid.uuid4().hex[:16]
        self.database.create_job(
            {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "engine": request.engine,
                "voice_id": request.voice_id,
                "language": request.language,
                "output_format": request.output_format,
                "text_preview": text[:160],
                "created_at": utc_now(),
            }
        )
        future = self.executor.submit(
            self._run,
            job_id,
            request,
            text,
            reference_audio,
        )
        with self.lock:
            self.futures[job_id] = future
        return self.database.get_job(job_id) or {}

    def _resolve_reference_audio(self, voice_id: str) -> Path | None:
        voice = self.database.get_voice(voice_id)
        return Path(voice["stored_path"]) if voice else None

    def _validate_voice(
        self,
        engine_id: str,
        voice_id: str,
        language: str,
        reference_audio: Path | None,
    ) -> None:
        engine = self.registry.get(engine_id)
        built_in = {voice.id: voice for voice in engine.info.voices}
        if reference_audio:
            if not engine.info.supports_cloning:
                raise ValueError(f"{engine.info.name} does not support cloned voices.")
            if not reference_audio.is_file():
                raise ValueError("The saved reference audio is missing.")
            return
        voice = built_in.get(voice_id)
        if not voice:
            raise ValueError(f"Voice '{voice_id}' is not available for {engine.info.name}.")
        if voice.language not in {language, "multi"}:
            raise ValueError(
                f"{voice.name} cannot speak {language}. Choose a voice listed for that language."
            )

    def _run(
        self,
        job_id: str,
        request: SynthesisRequest,
        text: str,
        reference_audio: Path | None,
    ) -> None:
        started = time.monotonic()
        temporary = self.output_dir / f"{job_id}.working.wav"
        destination = self.output_dir / f"{job_id}.{request.output_format}"

        try:
            self.database.update_job(job_id, status="running", progress=1)
            speech_text = self.translator.translate(
                text,
                request.language,
                lambda progress: self.database.update_job(
                    job_id,
                    progress=max(2, min(34, round(progress * 0.34))),
                ),
            )
            translated = speech_text if speech_text != text else None
            self.database.update_job(job_id, translated_text=translated, progress=35)

            def report(progress: int) -> None:
                mapped = 35 + round(progress * 0.59)
                self.database.update_job(job_id, progress=max(36, min(mapped, 94)))

            engine = self.registry.get(request.engine)
            engine.synthesize(
                GenerationInput(
                    text=speech_text,
                    voice_id=request.voice_id if reference_audio is None else "default",
                    language=request.language,
                    speed=request.speed,
                    reference_audio=reference_audio,
                ),
                temporary,
                report,
            )
            if request.engine.startswith("chatterbox-"):
                adjust_wav_speed(temporary, request.speed)
            self.database.update_job(job_id, progress=95)
            convert_wav(temporary, destination, request.output_format)
            self.database.update_job(
                job_id,
                status="complete",
                progress=100,
                output_path=str(destination),
                completed_at=utc_now(),
                generation_seconds=round(time.monotonic() - started, 3),
            )
        except Exception as error:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            self.database.update_job(
                job_id,
                status="failed",
                error=str(error),
                completed_at=utc_now(),
                generation_seconds=round(time.monotonic() - started, 3),
            )

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            future = self.futures.get(job_id)
        if not future or not future.cancel():
            return False
        self.database.update_job(
            job_id,
            status="cancelled",
            error="The job was cancelled before generation started.",
            completed_at=utc_now(),
        )
        return True

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
