from datetime import datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gradeflow_backend.utils.datetime import ensure_utc

from .base import Base


class GradingJobRecord(Base):
    __tablename__ = "grading_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # "run" | "preview"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def duration(self) -> timedelta | None:
        if self.completed_at is None:
            return None
        return ensure_utc(self.completed_at) - ensure_utc(self.created_at)

    @property
    def duration_seconds(self) -> float | None:
        duration = self.duration
        return duration.total_seconds() if duration is not None else None
