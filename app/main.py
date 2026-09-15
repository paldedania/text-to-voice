from __future__ import annotations

import unicodedata
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_DIR, Settings
from app.db import Database, utc_now
from app.engines.registry import EngineRegistry
from app.schemas import EngineResponse, JobResponse, SynthesisRequest, VoiceResponse
from app.services.jobs import JobManager, QueueFullError
from app.system import inspect_system

ALLOWED_REFERENCE_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def clean_voice_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name)
    clean = "".join(
        character for character in normalized if character.isalnum() or character in " _.-"
    )
    return clean.strip() or "Local voice"


def job_response(job: dict) -> JobResponse:
    output_path = job.get("output_path")
    audio_available = bool(output_path and Path(output_path).is_file())
    return JobResponse(
        **job,
        audio_url=f"/api/audio/{job['id']}" if audio_available else None,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    settings.prepare()
    database = Database(settings.database_path)
    database.initialize()
    database.fail_incomplete_jobs("Generation stopped because the app restarted.")
    registry = EngineRegistry()
    manager = JobManager(
        database,
        registry,
        settings.output_dir,
        max_queued_jobs=settings.max_queued_jobs,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(
        title="Text to Voice",
        description="A private local text-to-speech studio",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.registry = registry
    app.state.manager = manager

    @app.get("/api/system")
    async def system_status() -> dict:
        return inspect_system()

    @app.get("/api/engines", response_model=list[EngineResponse])
    async def list_engines() -> list[EngineResponse]:
        return [
            EngineResponse(
                id=engine.info.id,
                name=engine.info.name,
                description=engine.info.description,
                available=engine.info.available,
                availability_note=engine.info.availability_note,
                supports_cloning=engine.info.supports_cloning,
                supports_streaming=engine.info.supports_streaming,
                languages=list(engine.info.languages),
                voices=[
                    {"id": voice.id, "name": voice.name, "language": voice.language}
                    for voice in engine.info.voices
                ],
            )
            for engine in registry.all()
        ]

    @app.post("/api/synthesize", response_model=JobResponse, status_code=202)
    async def synthesize(request: SynthesisRequest) -> JobResponse:
        try:
            return job_response(manager.submit(request))
        except QueueFullError as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/jobs/{job_id}", response_model=JobResponse)
    async def get_job(job_id: str) -> JobResponse:
        job = database.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Generation job not found.")
        return job_response(job)

    @app.delete("/api/jobs/{job_id}", status_code=204)
    async def cancel_job(job_id: str) -> None:
        if not database.get_job(job_id):
            raise HTTPException(status_code=404, detail="Generation job not found.")
        if not manager.cancel(job_id):
            raise HTTPException(status_code=409, detail="Only queued jobs can be cancelled.")

    @app.get("/api/history", response_model=list[JobResponse])
    async def history() -> list[JobResponse]:
        return [job_response(job) for job in database.list_jobs()]

    @app.get("/api/audio/{job_id}")
    async def audio(job_id: str) -> FileResponse:
        job = database.get_job(job_id)
        if not job or job.get("status") != "complete" or not job.get("output_path"):
            raise HTTPException(status_code=404, detail="Generated audio is not available.")
        path = Path(job["output_path"])
        if not path.is_file() or path.parent.resolve() != settings.output_dir.resolve():
            raise HTTPException(status_code=404, detail="Generated audio file is missing.")
        return FileResponse(path, filename=path.name)

    @app.get("/api/voices", response_model=list[VoiceResponse])
    async def list_custom_voices() -> list[VoiceResponse]:
        voices = []
        voice_directory = settings.voices_dir.resolve()
        for voice in database.list_voices():
            path = Path(voice["stored_path"])
            if not path.is_file() or path.parent.resolve() != voice_directory:
                database.delete_voice(voice["id"])
                continue
            voices.append(VoiceResponse(**voice))
        return voices

    @app.post("/api/voices", response_model=VoiceResponse, status_code=201)
    async def create_voice(
        name: Annotated[str, Form(min_length=1, max_length=80)],
        consent: Annotated[bool, Form()],
        audio_file: Annotated[UploadFile, File()],
    ) -> VoiceResponse:
        if not consent:
            raise HTTPException(
                status_code=400,
                detail="Confirm that you own this voice or have permission to clone it.",
            )
        suffix = Path(audio_file.filename or "").suffix.lower()
        if suffix not in ALLOWED_REFERENCE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Use WAV, MP3, FLAC, OGG or M4A reference audio.",
            )
        content = await audio_file.read(settings.max_reference_bytes + 1)
        if len(content) > settings.max_reference_bytes:
            raise HTTPException(status_code=413, detail="Reference audio must be 20 MB or smaller.")
        if len(content) < 1_024:
            raise HTTPException(
                status_code=400, detail="The reference audio file is empty or invalid."
            )

        voice_id = uuid.uuid4().hex[:16]
        clean_name = clean_voice_name(name)
        destination = settings.voices_dir / f"{voice_id}{suffix}"
        destination.write_bytes(content)
        record = {
            "id": voice_id,
            "name": clean_name,
            "source_filename": Path(audio_file.filename or "reference").name,
            "stored_path": str(destination),
            "consent_version": "v1-owner-or-permission",
            "created_at": utc_now(),
        }
        try:
            database.create_voice(record)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return VoiceResponse(**record)

    @app.delete("/api/voices/{voice_id}", status_code=204)
    async def delete_voice(voice_id: str) -> None:
        voice = database.get_voice(voice_id)
        if not voice:
            raise HTTPException(status_code=404, detail="Saved voice not found.")

        path = Path(voice["stored_path"])
        if path.parent.resolve() == settings.voices_dir.resolve():
            path.unlink(missing_ok=True)
        database.delete_voice(voice_id)

    static_dir = PROJECT_DIR / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
