from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    engine TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    text_preview TEXT NOT NULL,
                    translated_text TEXT,
                    output_path TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    generation_seconds REAL
                );
                CREATE INDEX IF NOT EXISTS jobs_created_at_idx
                    ON jobs(created_at DESC);

                CREATE TABLE IF NOT EXISTS voices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    consent_version TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS voices_created_at_idx
                    ON voices(created_at DESC);
                """
            )
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "translated_text" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN translated_text TEXT")

    def create_job(self, values: dict[str, Any]) -> None:
        columns = ", ".join(values)
        placeholders = ", ".join(f":{name}" for name in values)
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",  # noqa: S608
                values,
            )

    def update_job(self, job_id: str, **values: Any) -> None:
        if not values:
            return
        assignments = ", ".join(f"{name} = :{name}" for name in values)
        values["id"] = job_id
        with self.connect() as connection:
            connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = :id",  # noqa: S608
                values,
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_voice(self, values: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO voices
                    (id, name, source_filename, stored_path, consent_version, created_at)
                VALUES
                    (:id, :name, :source_filename, :stored_path, :consent_version, :created_at)
                """,
                values,
            )

    def get_voice(self, voice_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM voices WHERE id = ?",
                (voice_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_voices(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM voices ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]
