import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.config import Settings
from app.main import create_app


async def asgi_request(
    app: FastAPI,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(json_body).encode() if json_body is not None else b""
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
