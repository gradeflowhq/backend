from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base


class SubmissionRecord(Base):
    __tablename__ = "submission_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(String(255))
    answer_map: Mapped[dict] = mapped_column(JSON)

    results: Mapped[list["SubmissionResult"]] = relationship(
        "SubmissionResult",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (UniqueConstraint("assessment_id", "student_id"),)


class SubmissionResult(Base):
    __tablename__ = "submission_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("submission_records.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(String(255))
    output: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    feedback: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(String(255))
    graded: Mapped[bool] = mapped_column(Boolean)
    points: Mapped[float] = mapped_column(Float)
    max_points: Mapped[float] = mapped_column(Float)
    adjusted_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    adjusted_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission: Mapped["SubmissionRecord"] = relationship(
        "SubmissionRecord", back_populates="results"
    )

    __table_args__ = (UniqueConstraint("submission_id", "question_id"),)
