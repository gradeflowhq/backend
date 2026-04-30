import uuid

from gradeflow_engine.submissions.models import Submission
from sqlalchemy import delete, func, insert, select, tuple_, update
from sqlalchemy.orm import Session

from gradeflow_backend.models.submission import SubmissionRecord, SubmissionResult
from gradeflow_backend.schemas.grading import AdjustableQuestionResult, AdjustableSubmission

from .base import BaseRepository


class SubmissionRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def bulk_upsert(
        self,
        assessment_id: str,
        submissions: list[Submission],
        *,
        remove_adjustments: bool = False,
    ) -> None:
        """Upsert graded submissions for an assessment:

        - Update existing submissions (by student_id), preserving manual adjustments
          unless ``remove_adjustments=True``.
        - Delete submissions for student IDs no longer present in new results.
        - Insert submissions for new student IDs.

        All SQL operations are batched to avoid O(n) round-trips.
        """
        existing = {r.student_id: r for r in self.list_by_assessment(assessment_id)}
        new_by_student = {s.student_id: s for s in submissions}

        # 1. Batch-delete non-matching student records.
        to_delete_sids = set(existing.keys()) - set(new_by_student.keys())
        if to_delete_sids:
            self.session().execute(
                delete(SubmissionRecord).where(
                    SubmissionRecord.assessment_id == assessment_id,
                    SubmissionRecord.student_id.in_(to_delete_sids),
                )
            )

        existing_update_sids = set(existing.keys()) & set(new_by_student.keys())
        existing_update_ids = [existing[sid].id for sid in existing_update_sids]

        # 2. Snapshot adjustments for all records being updated (already selectin-loaded).
        adj_by_sub: dict[str, dict[str, tuple[float | None, str | None]]] = (
            {}
            if remove_adjustments
            else {
                rec.id: {
                    r.question_id: (r.adjusted_points, r.adjusted_feedback) for r in rec.results
                }
                for rec in existing.values()
                if rec.student_id in new_by_student
            }
        )

        # 3. Batch-update answer_maps for existing submissions (single executemany).
        update_rows = [
            {"id": existing[sid].id, "answer_map": dict(new_by_student[sid].answer_map)}
            for sid in existing_update_sids
        ]
        if update_rows:
            self.session().execute(update(SubmissionRecord), update_rows)

        # 4. Batch-delete all results for updated submission IDs (single IN query).
        if existing_update_ids:
            self.session().execute(
                delete(SubmissionResult).where(
                    SubmissionResult.submission_id.in_(existing_update_ids)
                )
            )

        # 5. Build and insert result and record rows in two bulk inserts.
        new_record_rows: list[dict] = []
        new_result_rows: list[dict] = []

        for sub in submissions:
            if sub.student_id in existing:
                rec = existing[sub.student_id]
                adj_map = adj_by_sub.get(rec.id, {})
                for qid, r in sub.result_map.items():
                    adj_pts, adj_fb = adj_map.get(qid, (None, None))
                    new_result_rows.append(
                        {
                            "id": uuid.uuid4().hex,
                            "submission_id": rec.id,
                            "question_id": qid,
                            "output": float(r.output),
                            "passed": r.passed,
                            "feedback": r.feedback,
                            "rule": r.rule,
                            "graded": r.graded,
                            "points": r.points,
                            "max_points": r.max_points,
                            "adjusted_points": adj_pts,
                            "adjusted_feedback": adj_fb,
                        }
                    )
            else:
                sub_id = uuid.uuid4().hex
                new_record_rows.append(
                    {
                        "id": sub_id,
                        "assessment_id": assessment_id,
                        "student_id": sub.student_id,
                        "answer_map": dict(sub.answer_map),
                    }
                )
                for qid, r in sub.result_map.items():
                    new_result_rows.append(
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
                            "adjusted_points": None,
                            "adjusted_feedback": None,
                        }
                    )

        if new_record_rows:
            self.session().execute(insert(SubmissionRecord), new_record_rows)
        if new_result_rows:
            self.session().execute(insert(SubmissionResult), new_result_rows)
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

    def count_graded_by_assessment(self, assessment_id: str) -> int:
        """Return the number of graded student records for an assessment."""
        stmt = (
            select(func.count())
            .select_from(SubmissionRecord)
            .where(SubmissionRecord.assessment_id == assessment_id)
        )
        return self.session().execute(stmt).scalar_one()

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

    def bulk_get_results(
        self,
        assessment_id: str,
        student_question_pairs: list[tuple[str, str]],
    ) -> dict[tuple[str, str], SubmissionResult]:
        """Fetch multiple results in a single query.

        Returns a dict keyed by (student_id, question_id).
        """
        if not student_question_pairs:
            return {}
        stmt = (
            select(SubmissionResult, SubmissionRecord.student_id)
            .join(SubmissionRecord, SubmissionResult.submission_id == SubmissionRecord.id)
            .where(
                SubmissionRecord.assessment_id == assessment_id,
                tuple_(SubmissionRecord.student_id, SubmissionResult.question_id).in_(
                    student_question_pairs
                ),
            )
        )
        rows = self.session().execute(stmt).all()
        return {(student_id, result.question_id): result for result, student_id in rows}

    @staticmethod
    def to_adjustable_submission(submission_record: SubmissionRecord) -> AdjustableSubmission:
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
            for r in submission_record.results
        }
        return AdjustableSubmission(
            student_id=submission_record.student_id,
            answer_map=submission_record.answer_map,
            result_map=result_map,
        )
