"""SQLite repository implementation for framework-independent job messages."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.interfaces import JobRepositoryProtocol
from models.job_application import JobApplication
from models.job_details import JobDetails
from models.job_message import JobMessage


logger = logging.getLogger(__name__)
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "jobs.db"


class JobRepository(JobRepositoryProtocol):
    """Persist and retrieve :class:`JobMessage` records from SQLite."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self._database_path = Path(database_path)
        self._connection: sqlite3.Connection | None = None

    def init(self) -> None:
        """Open the database and create the jobs table when necessary."""

        if self._connection is not None:
            return

        try:
            self._connection = sqlite3.connect(self._database_path)
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL UNIQUE,
                    channel_name TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    urls TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    media_present INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    final_apply_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    experience TEXT,
                    salary TEXT,
                    employment_type TEXT,
                    work_mode TEXT,
                    skills TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(message_id, source_url),
                    FOREIGN KEY(message_id) REFERENCES jobs(message_id)
                )
                """
            )
            self._connection.commit()
            logger.info("SQLite jobs database initialized at %s", self._database_path)
        except sqlite3.Error:
            logger.exception("Unable to initialize SQLite jobs database")
            self.close()

    def save(self, job: JobMessage) -> bool:
        """Save a job, returning ``False`` if it is already stored or cannot save."""

        if not isinstance(job, JobMessage):
            raise TypeError("JobRepository.save accepts only JobMessage instances")

        connection = self._get_connection()
        if connection is None:
            return False

        try:
            cursor = connection.execute(
                """
                INSERT INTO jobs (
                    message_id, channel_name, message_text, urls, received_at,
                    source, media_present, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO NOTHING
                """,
                (
                    job.message_id,
                    job.channel_name,
                    job.message_text,
                    json.dumps(job.urls),
                    job.received_at.isoformat(),
                    job.source,
                    int(job.media_present),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()

            saved = cursor.rowcount == 1
            if saved:
                logger.info("Saved JobMessage message_id=%d", job.message_id)
            else:
                logger.info("Skipped duplicate JobMessage message_id=%d", job.message_id)
            return saved
        except (sqlite3.Error, TypeError, ValueError):
            logger.exception("Unable to save JobMessage message_id=%d", job.message_id)
            return False

    def job_exists(self, message_id: int) -> bool:
        """Return whether a job with the source message ID is already stored."""

        connection = self._get_connection()
        if connection is None:
            return False

        try:
            row = connection.execute(
                "SELECT 1 FROM jobs WHERE message_id = ? LIMIT 1", (message_id,)
            ).fetchone()
            return row is not None
        except sqlite3.Error:
            logger.exception("Unable to check JobMessage message_id=%d", message_id)
            return False

    def get_job(self, message_id: int) -> JobMessage | None:
        """Return a stored job by source message ID, if it exists."""

        connection = self._get_connection()
        if connection is None:
            return None

        try:
            row = connection.execute(
                """
                SELECT message_id, channel_name, message_text, urls, received_at,
                       source, media_present
                FROM jobs
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
            return self._row_to_job_message(row) if row is not None else None
        except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
            logger.exception("Unable to retrieve JobMessage message_id=%d", message_id)
            return None

    def get_all_jobs(self) -> list[JobMessage]:
        """Return every stored job in insertion order."""

        connection = self._get_connection()
        if connection is None:
            return []

        try:
            rows = connection.execute(
                """
                SELECT message_id, channel_name, message_text, urls, received_at,
                       source, media_present
                FROM jobs
                ORDER BY id ASC
                """
            ).fetchall()
            return [self._row_to_job_message(row) for row in rows]
        except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
            logger.exception("Unable to retrieve stored JobMessages")
            return []

    def save_job_application(
        self,
        message_id: int,
        source_url: str,
        final_apply_url: str,
        details: JobDetails,
    ) -> bool:
        """Store resolved URL and structured details for one source job link."""

        if not isinstance(details, JobDetails):
            raise TypeError("details must be a JobDetails instance")

        connection = self._get_connection()
        if connection is None:
            return False

        try:
            connection.execute(
                """
                INSERT INTO job_applications (
                    message_id, source_url, final_apply_url, title, company,
                    location, experience, salary, employment_type, work_mode,
                    skills, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, source_url) DO UPDATE SET
                    final_apply_url = excluded.final_apply_url,
                    title = excluded.title,
                    company = excluded.company,
                    location = excluded.location,
                    experience = excluded.experience,
                    salary = excluded.salary,
                    employment_type = excluded.employment_type,
                    work_mode = excluded.work_mode,
                    skills = excluded.skills,
                    description = excluded.description
                """,
                (
                    message_id,
                    source_url,
                    final_apply_url,
                    details.title,
                    details.company,
                    details.location,
                    details.experience,
                    details.salary,
                    details.employment_type,
                    details.work_mode,
                    json.dumps(details.skills),
                    details.description,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
            logger.info("Saved resolved application message_id=%d source_url=%s", message_id, source_url)
            return True
        except (sqlite3.Error, TypeError, ValueError):
            logger.exception("Unable to save resolved application for message_id=%d", message_id)
            return False

    def get_job_applications(self) -> list[JobApplication]:
        """Return every resolved application and its final-page details."""

        connection = self._get_connection()
        if connection is None:
            return []

        try:
            rows = connection.execute(
                """
                SELECT message_id, source_url, final_apply_url, title, company,
                       location, experience, salary, employment_type, work_mode,
                       skills, description
                FROM job_applications
                ORDER BY id ASC
                """
            ).fetchall()
            return [self._row_to_job_application(row) for row in rows]
        except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
            logger.exception("Unable to retrieve resolved job applications")
            return []

    def close(self) -> None:
        """Close the open SQLite connection, if any."""

        if self._connection is None:
            return

        try:
            self._connection.close()
        except sqlite3.Error:
            logger.exception("Unable to close SQLite jobs database")
        finally:
            self._connection = None

    def _get_connection(self) -> sqlite3.Connection | None:
        self.init()
        return self._connection

    @staticmethod
    def _row_to_job_message(row: tuple[object, ...]) -> JobMessage:
        return JobMessage(
            message_id=int(row[0]),
            channel_name=str(row[1]),
            message_text=str(row[2]),
            urls=json.loads(str(row[3])),
            received_at=datetime.fromisoformat(str(row[4])),
            source=str(row[5]),
            media_present=bool(row[6]),
        )

    @staticmethod
    def _row_to_job_application(row: tuple[object, ...]) -> JobApplication:
        return JobApplication(
            message_id=int(row[0]),
            source_url=str(row[1]),
            final_apply_url=str(row[2]),
            details=JobDetails(
                title=str(row[3]),
                company=str(row[4]),
                location=str(row[5]) if row[5] is not None else None,
                experience=str(row[6]) if row[6] is not None else None,
                salary=str(row[7]) if row[7] is not None else None,
                employment_type=str(row[8]) if row[8] is not None else None,
                work_mode=str(row[9]) if row[9] is not None else None,
                skills=json.loads(str(row[10])),
                description=str(row[11]),
                apply_url=str(row[2]),
            ),
        )
