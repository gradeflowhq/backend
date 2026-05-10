from datetime import datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from gradeflow_backend.schemas.grading import JobStatus, JobType
from gradeflow_backend.utils.datetime import ensure_utc

from .base import Base


class GradingJobRecord(Base):
    __tablename__ = "grading_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[JobType] = mapped_column(String(16), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        String(16), nullable=False, default="queued", server_default="queued"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_finished(self) -> bool:
        return self.status in {"completed", "failed"}

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def duration(self) -> timedelta | None:
        if not self.is_finished or self.finished_at is None:
            return None
        return ensure_utc(self.finished_at) - ensure_utc(self.created_at)

    @property
    def duration_seconds(self) -> float | None:
        duration = self.duration
        return duration.total_seconds() if duration is not None else None
