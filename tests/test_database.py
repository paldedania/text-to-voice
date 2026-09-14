from pathlib import Path

from app.db import Database


def test_job_and_voice_round_trip(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    database.create_job(
        {
            "id": "job-one",
            "status": "queued",
            "progress": 0,
            "engine": "diagnostic",
            "voice_id": "signal",
            "language": "en",
            "output_format": "wav",
            "text_preview": "Test",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    database.update_job("job-one", status="complete", progress=100)

    job = database.get_job("job-one")
    assert job is not None
    assert job["status"] == "complete"
    assert job["progress"] == 100

    database.create_voice(
        {
            "id": "voice-one",
            "name": "My voice",
            "source_filename": "reference.wav",
            "stored_path": str(tmp_path / "voice.wav"),
            "consent_version": "v1-owner-or-permission",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert database.get_voice("voice-one")["name"] == "My voice"
