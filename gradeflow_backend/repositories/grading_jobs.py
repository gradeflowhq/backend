from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.config import get_settings
from gradeflow_backend.models.grading_job import GradingJobRecord
from gradeflow_backend.schemas.grading import JobType
from gradeflow_backend.utils.datetime import utcnow

from .base import BaseRepository

TerminalJobStatus = Literal["completed", "failed"]


class GradingJobRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        grading_settings = get_settings().grading
        self._estimate_sample_size = grading_settings.completed_job_estimate_sample_size
        self._estimate_ewma_alpha = grading_settings.completed_job_estimate_ewma_alpha

    def create(self, assessment_id: str, job_type: JobType, job_id: str) -> GradingJobRecord:
        record = GradingJobRecord(
            job_id=job_id,
            assessment_id=assessment_id,
            type=job_type,
            status="queued",
        )
        self.session().add(record)
        self.session().flush()
        self.session().refresh(record)
        return record

    def get(self, job_id: str) -> GradingJobRecord:
        record = self.session().get(GradingJobRecord, job_id)
        if record is None:
            raise NoResultFound(f"Grading job {job_id} not found")
        return record

    def delete(self, job_id: str) -> None:
        record = self.get(job_id)
        self.session().delete(record)
        self.session().flush()

    def get_latest(self, assessment_id: str, job_type: JobType) -> GradingJobRecord | None:
        stmt = (
            select(GradingJobRecord)
            .where(
                GradingJobRecord.assessment_id == assessment_id,
                GradingJobRecord.type == job_type,
            )
            .order_by(GradingJobRecord.created_at.desc())
        )
        return self.session().execute(stmt).scalars().first()

    def mark_running(self, job_id: str) -> GradingJobRecord:
        record = self.get(job_id)
        if not record.is_finished and record.status != "running":
            record.status = "running"
            self.session().flush()
        return record

    def mark_completed(self, job_id: str) -> GradingJobRecord:
        return self._mark_finished(
            job_id,
            status="completed",
            error=None,
        )

    def mark_failed(
        self,
        job_id: str,
        *,
        error: str | None = None,
    ) -> GradingJobRecord:
        return self._mark_finished(
            job_id,
            status="failed",
            error=error,
        )

    def _mark_finished(
        self,
        job_id: str,
        *,
        status: TerminalJobStatus,
        error: str | None,
    ) -> GradingJobRecord:
        record = self.get(job_id)
        if record.is_completed and status == "failed":
            return record

        if record.status != status or record.finished_at is None:
            record.finished_at = utcnow()

        record.status = status
        record.error = error
        self.session().flush()
        return record

    def estimate_duration_seconds(self, assessment_id: str, job_type: JobType) -> float | None:
        estimate = self._ewma_completed_duration_seconds(
            job_type=job_type,
            assessment_id=assessment_id,
        )
        if estimate is not None:
            return estimate

        return self._ewma_completed_duration_seconds(job_type=job_type)

    def _ewma_completed_duration_seconds(
        self,
        *,
        job_type: JobType,
        assessment_id: str | None = None,
    ) -> float | None:
        stmt = select(GradingJobRecord).where(
            GradingJobRecord.type == job_type,
            GradingJobRecord.status == "completed",
            GradingJobRecord.finished_at.is_not(None),
        )
        if assessment_id is not None:
            stmt = stmt.where(GradingJobRecord.assessment_id == assessment_id)
        stmt = stmt.order_by(
            GradingJobRecord.finished_at.desc(),
            GradingJobRecord.created_at.desc(),
        ).limit(self._estimate_sample_size)

        recent_durations = cast(
            list[float],
            [record.duration_seconds for record in self.session().execute(stmt).scalars()],
        )
        recent_durations.reverse()
        if not recent_durations:
            return None

        estimate = recent_durations[0]
        for duration_seconds in recent_durations[1:]:
            estimate = (
                self._estimate_ewma_alpha * duration_seconds
                + (1 - self._estimate_ewma_alpha) * estimate
            )
        return round(estimate, 3)
