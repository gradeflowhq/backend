import uuid

from gradeflow_engine.submissions.models import Submission
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from gradeflow_backend.models.submission import SubmissionRecord, SubmissionResult
from gradeflow_backend.schemas.grading import AdjustableQuestionResult, AdjustableSubmission

from .base import BaseRepository


class SubmissionRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def bulk_replace(self, assessment_id: str, submissions: list[Submission]) -> None:
        """Delete all existing graded submissions for the assessment and insert fresh ones."""
        self.session().execute(
            delete(SubmissionRecord).where(SubmissionRecord.assessment_id == assessment_id)
        )

        record_rows = []
        result_rows = []
        for sub in submissions:
            sub_id = uuid.uuid4().hex
            record_rows.append(
                {
                    "id": sub_id,
                    "assessment_id": assessment_id,
                    "student_id": sub.student_id,
                    "answer_map": dict(sub.answer_map),
                }
            )
            for qid, r in sub.result_map.items():
                result_rows.append(
                    {
                        "id": uuid.uuid4().hex,
                        "submission_id": sub_id,
                        "question_id": qid,
                        "output": float(r.output),
                        "passed": r.passed,
                        "feedback": r.feedback,
                        "rule": r.rule,
                        "graded": r.graded,
                        "points": r.points,
                        "max_points": r.max_points,
                        "adjusted_points": getattr(r, "adjusted_points", None),
                        "adjusted_feedback": getattr(r, "adjusted_feedback", None),
                    }
                )

        if record_rows:
            self.session().execute(insert(SubmissionRecord), record_rows)
        if result_rows:
            self.session().execute(insert(SubmissionResult), result_rows)
        self.session().flush()

    def list_by_assessment(self, assessment_id: str) -> list[SubmissionRecord]:
        stmt = (
            select(SubmissionRecord)
            .where(SubmissionRecord.assessment_id == assessment_id)
            .order_by(SubmissionRecord.student_id)
        )
        return list(self.session().execute(stmt).scalars().all())

    def delete_by_assessment(self, assessment_id: str) -> None:
        self.session().execute(
            delete(SubmissionRecord).where(SubmissionRecord.assessment_id == assessment_id)
        )
        self.session().flush()

    def update_result(
        self,
        result: SubmissionResult,
        adjusted_points: float | None,
        adjusted_feedback: str | None,
    ) -> None:
        """Apply an adjustment to a SubmissionResult row and flush."""
        result.adjusted_points = adjusted_points
        result.adjusted_feedback = adjusted_feedback
        result.graded = True
        self.session().flush()

    def get_result(
        self, assessment_id: str, student_id: str, question_id: str
    ) -> SubmissionResult | None:
        stmt = (
            select(SubmissionResult)
            .join(SubmissionRecord, SubmissionResult.submission_id == SubmissionRecord.id)
            .where(
                SubmissionRecord.assessment_id == assessment_id,
                SubmissionRecord.student_id == student_id,
                SubmissionResult.question_id == question_id,
            )
        )
        return self.session().execute(stmt).scalar_one_or_none()

    @staticmethod
    def to_adjustable_submission(gs: SubmissionRecord) -> AdjustableSubmission:
        result_map = {
            r.question_id: AdjustableQuestionResult(
                output=r.output,
                passed=r.passed,
                feedback=r.feedback,
                rule=r.rule,
                graded=r.graded,
                points=r.points,
                max_points=r.max_points,
                adjusted_points=r.adjusted_points,
                adjusted_feedback=r.adjusted_feedback,
            )
            for r in gs.results
        }
        return AdjustableSubmission(
            student_id=gs.student_id,
            answer_map=gs.answer_map,
            result_map=result_map,
        )
