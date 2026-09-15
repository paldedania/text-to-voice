import asyncio
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from app.config import Settings
from app.db import Database
from app.main import create_app


async def asgi_request(
    app: FastAPI,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    request_headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = (
        raw_body
        if raw_body is not None
        else (json.dumps(json_body).encode() if json_body is not None else b"")
    )
    messages: list[dict[str, Any]] = []
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    headers = [(b"host", b"test")]
    if json_body is not None:
        headers.append((b"content-type", b"application/json"))
    if request_headers:
        headers.extend(request_headers)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
        "state": {},
    }
    await app(scope, receive, send)

    start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(response_body or b"{}")


def test_diagnostic_job_completes(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, job = await asgi_request(
                app,
                "POST",
                "/api/synthesize",
                {
                    "text": "Test the queue and audio player.",
                    "engine": "diagnostic",
                    "voice_id": "signal",
                    "language": "en",
                    "speed": 1,
                    "output_format": "wav",
                },
            )
            assert status == 202

            for _attempt in range(150):
                if job["status"] in {"complete", "failed"}:
                    break
                await asyncio.sleep(0.02)
                status, job = await asgi_request(app, "GET", f"/api/jobs/{job['id']}")
                assert status == 200

            assert job["status"] == "complete"
            assert job["progress"] == 100
            stored_job = app.state.database.get_job(job["id"])
            assert stored_job is not None
            assert Path(stored_job["output_path"]).is_file()
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_rejects_unknown_engine(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, body = await asgi_request(
                app,
                "POST",
                "/api/synthesize",
                {
                    "text": "Test",
                    "engine": "missing-engine",
                    "voice_id": "default",
                    "language": "en",
                    "speed": 1,
                    "output_format": "wav",
                },
            )
            assert status == 400
            assert "Unknown speech engine" in body["detail"]
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_rejects_voice_from_wrong_language(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, body = await asgi_request(
                app,
                "POST",
                "/api/synthesize",
                {
                    "text": "Translate this into Hindi.",
                    "engine": "kokoro",
                    "voice_id": "af_heart",
                    "language": "hi",
                    "speed": 1,
                    "output_format": "wav",
                },
            )
            assert status == 400
            assert "cannot speak hi" in body["detail"]
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_rejects_job_when_generation_queue_is_full(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
        max_queued_jobs=0,
    )

    async def run_test() -> None:
        app = create_app(settings)
        request = {
            "text": "word " * 100,
            "engine": "diagnostic",
            "voice_id": "signal",
            "language": "en",
            "speed": 1,
            "output_format": "wav",
        }
        try:
            first_status, _first_job = await asgi_request(
                app,
                "POST",
                "/api/synthesize",
                request,
            )
            second_status, second_body = await asgi_request(
                app,
                "POST",
                "/api/synthesize",
                request,
            )

            assert first_status == 202
            assert second_status == 429
            assert second_body["detail"] == "The generation queue is full. Try again later."
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_history_hides_audio_link_when_generated_file_is_missing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            app.state.database.create_job(
                {
                    "id": "missing-audio",
                    "status": "complete",
                    "progress": 100,
                    "engine": "diagnostic",
                    "voice_id": "signal",
                    "language": "en",
                    "output_format": "wav",
                    "text_preview": "Missing output",
                    "output_path": str(settings.output_dir / "missing-audio.wav"),
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            )

            status, jobs = await asgi_request(app, "GET", "/api/history")

            assert status == 200
            assert jobs[0]["status"] == "complete"
            assert jobs[0]["audio_url"] is None
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_delete_voice_removes_record_and_local_audio(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        voice_path = settings.voices_dir / "voice-one.wav"
        voice_path.write_bytes(b"RIFF" + b"\0" * 1_020)
        app.state.database.create_voice(
            {
                "id": "voice-one",
                "name": "My voice",
                "source_filename": "reference.wav",
                "stored_path": str(voice_path),
                "consent_version": "v1-owner-or-permission",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        try:
            status, _body = await asgi_request(app, "DELETE", "/api/voices/voice-one")

            assert status == 204
            assert app.state.database.get_voice("voice-one") is None
            assert not voice_path.exists()
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_voice_list_removes_records_whose_audio_is_missing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        app.state.database.create_voice(
            {
                "id": "missing-voice",
                "name": "Missing voice",
                "source_filename": "missing.wav",
                "stored_path": str(settings.voices_dir / "missing.wav"),
                "consent_version": "v1-owner-or-permission",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        try:
            status, voices = await asgi_request(app, "GET", "/api/voices")

            assert status == 200
            assert voices == []
            assert app.state.database.get_voice("missing-voice") is None
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_rejects_text_containing_only_invisible_unicode(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, body = await asgi_request(
                app,
                "POST",
                "/api/synthesize",
                {
                    "text": "\u200b\u2060",
                    "engine": "diagnostic",
                    "voice_id": "signal",
                    "language": "en",
                    "speed": 1,
                    "output_format": "wav",
                },
            )

            assert status == 422
            assert body["detail"][0]["msg"] == "Value error, Enter text before generating speech."
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_system_status_survives_nvidia_smi_timeout(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )

    monkeypatch.setattr(
        "app.system.shutil.which",
        lambda command: "/usr/bin/nvidia-smi" if command == "nvidia-smi" else None,
    )

    def time_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("nvidia-smi", 5)

    monkeypatch.setattr("app.system.subprocess.run", time_out)

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, body = await asgi_request(app, "GET", "/api/system")

            assert status == 200
            assert body["nvidia"]["ready"] is False
            assert body["nvidia"]["detail"] == "nvidia-smi timed out after 5 seconds"
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_failed_voice_save_does_not_leave_recording_on_disk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )
    boundary = "voice-upload-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="name"\r\n\r\n'
            "My voice\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="consent"\r\n\r\n'
            "true\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="audio_file"; filename="sample.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + b"RIFF"
        + b"\0" * 1_020
        + f"\r\n--{boundary}--\r\n".encode()
    )

    async def run_test() -> None:
        app = create_app(settings)

        def fail_to_save(_record: dict[str, Any]) -> None:
            raise sqlite3.OperationalError("database unavailable")

        monkeypatch.setattr(app.state.database, "create_voice", fail_to_save)
        try:
            with pytest.raises(sqlite3.OperationalError, match="database unavailable"):
                await asgi_request(
                    app,
                    "POST",
                    "/api/voices",
                    raw_body=body,
                    request_headers=[
                        (b"content-type", f"multipart/form-data; boundary={boundary}".encode())
                    ],
                )

            assert list(settings.voices_dir.iterdir()) == []
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_voice_upload_preserves_unicode_name(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )
    boundary = "unicode-voice-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="name"\r\n\r\n'
            "我的声音\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="consent"\r\n\r\n'
            "true\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="audio_file"; filename="sample.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + b"RIFF"
        + b"\0" * 1_020
        + f"\r\n--{boundary}--\r\n".encode()
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, voice = await asgi_request(
                app,
                "POST",
                "/api/voices",
                raw_body=body,
                request_headers=[
                    (b"content-type", f"multipart/form-data; boundary={boundary}".encode())
                ],
            )

            assert status == 201
            assert voice["name"] == "我的声音"
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())


def test_startup_marks_interrupted_jobs_as_failed(tmp_path: Path) -> None:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        output_dir=data / "output",
        voices_dir=data / "voices",
        database_path=data / "test.sqlite3",
    )
    settings.prepare()
    database = Database(settings.database_path)
    database.initialize()
    database.create_job(
        {
            "id": "interrupted-job",
            "status": "running",
            "progress": 42,
            "engine": "kokoro",
            "voice_id": "af_heart",
            "language": "en",
            "output_format": "wav",
            "text_preview": "Interrupted",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )

    async def run_test() -> None:
        app = create_app(settings)
        try:
            status, jobs = await asgi_request(app, "GET", "/api/history")

            assert status == 200
            assert jobs[0]["status"] == "failed"
            assert jobs[0]["error"] == "Generation stopped because the app restarted."
            assert jobs[0]["completed_at"] is not None
        finally:
            app.state.manager.shutdown()

    asyncio.run(run_test())
