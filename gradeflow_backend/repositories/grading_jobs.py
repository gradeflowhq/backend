from typing import Literal
from typing import cast as type_cast

from sqlalchemy import Float, func, select, text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from gradeflow_backend.config import get_settings
from gradeflow_backend.models.grading_job import GradingJobRecord
from gradeflow_backend.schemas.grading import JobType
from gradeflow_backend.utils.datetime import utcnow

from .base import BaseRepository

TerminalJobStatus = Literal["completed", "failed"]


class GradingJobRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._estimate_sample_size = get_settings().grading.completed_job_estimate_sample_size

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
        estimate = self._average_completed_duration_seconds(
            job_type=job_type,
            assessment_id=assessment_id,
        )
        if estimate is not None:
            return estimate

        return self._average_completed_duration_seconds(job_type=job_type)

    def _duration_seconds_expression(self) -> ColumnElement[float]:
        dialect_name = self.session().get_bind().dialect.name
        if dialect_name == "sqlite":
            return type_cast(
                ColumnElement[float],
                (
                    (
                        func.julianday(GradingJobRecord.finished_at)
                        - func.julianday(GradingJobRecord.created_at)
                    )
                    * 86400.0
                ).cast(Float),
            )
        if dialect_name in {"mysql", "mariadb"}:
            return type_cast(
                ColumnElement[float],
                func.timestampdiff(
                    text("SECOND"),
                    GradingJobRecord.created_at,
                    GradingJobRecord.finished_at,
                ).cast(Float),
            )
        return type_cast(
            ColumnElement[float],
            func.extract(
                "epoch",
                GradingJobRecord.finished_at - GradingJobRecord.created_at,
            ).cast(Float),
        )

    def _completed_duration_seconds_stmt(
        self,
        *,
        job_type: JobType,
        assessment_id: str | None = None,
    ) -> Select[tuple[float]]:
        duration_seconds = self._duration_seconds_expression().label("duration_seconds")
        stmt = select(duration_seconds).where(
            GradingJobRecord.type == job_type,
            GradingJobRecord.status == "completed",
            GradingJobRecord.finished_at.is_not(None),
            GradingJobRecord.finished_at >= GradingJobRecord.created_at,
        )
        if assessment_id is not None:
            stmt = stmt.where(GradingJobRecord.assessment_id == assessment_id)
        return stmt.order_by(
            GradingJobRecord.finished_at.desc(),
            GradingJobRecord.created_at.desc(),
        ).limit(self._estimate_sample_size)

    def _average_completed_duration_seconds(
        self,
        *,
        job_type: JobType,
        assessment_id: str | None = None,
    ) -> float | None:
        recent_durations = self._completed_duration_seconds_stmt(
            job_type=job_type,
            assessment_id=assessment_id,
        ).subquery()
        stmt = select(func.avg(recent_durations.c.duration_seconds))
        estimate = self.session().execute(stmt)
        average = estimate.scalar_one()
        return round(float(average), 3) if average is not None else None
