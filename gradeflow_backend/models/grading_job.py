from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GradingJobRecord(Base):
    __tablename__ = "grading_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # "run" | "preview"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
