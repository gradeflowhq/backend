import csv
import io
from datetime import datetime

import yaml
from gradeflow_engine.exceptions import GradeFlowError
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.repositories.submissions import SubmissionRepository
from gradeflow_backend.schemas.assessments import (
    AssessmentCoverage,
    AssessmentCreateRequest,
    AssessmentResponse,
    AssessmentSummary,
    AssessmentUpdateRequest,
)
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.utils.datetime import ensure_utc


def _effective_updated_at(a: Assessment) -> datetime:
    candidates: list[datetime | None] = [
        a.updated_at,
        a.question_set_updated_at,
        a.rubric_updated_at,
        a.source_updated_at,
        a.results_updated_at,
    ]
    return max(ensure_utc(dt) for dt in candidates if dt is not None)


def _count_csv_rows(source_data: str) -> int:
    """Count data rows (excluding header) in a CSV string cheaply."""
    reader = csv.reader(io.StringIO(source_data))
    rows = sum(1 for row in reader if any(cell.strip() for cell in row))
    return max(0, rows - 1)  # subtract header


def _count_questions(question_set_yaml: str) -> int:
    """Count questions in a YAML question set string."""
    try:
        data = yaml.safe_load(question_set_yaml)
        if isinstance(data, dict):
            qmap = data.get("question_map", data)
            if isinstance(qmap, dict):
                return len(qmap)
    except yaml.YAMLError:
        pass
    return 0


def _compute_coverage(a: Assessment) -> AssessmentCoverage | None:
    """Compute rubric coverage synchronously for the given assessment."""
    if not a.rubric_yaml or not a.question_set_yaml:
        return None
    try:
        rubric_data = yaml.safe_load(a.rubric_yaml)
        rubric = Rubric.model_validate(rubric_data)
        qs_data = yaml.safe_load(a.question_set_yaml)
        question_set = QuestionSet.model_validate(qs_data)
        cov = rubric.get_coverage(question_set)
        return AssessmentCoverage(
            total=cov.total,
            covered=cov.covered,
            percentage=cov.percentage,
        )
    except Exception as e:
        raise GradeFlowError(f"Failed to compute rubric coverage: {e}") from e


def _build_summary(a: Assessment, submission_repo: SubmissionRepository) -> AssessmentSummary:
    submission_count = _count_csv_rows(a.source_data) if a.source_data else None
    question_count = _count_questions(a.question_set_yaml) if a.question_set_yaml else None
    graded_count = submission_repo.count_graded_by_assessment(a.id)
    coverage = _compute_coverage(a)
    return AssessmentSummary(
        submission_count=submission_count,
        question_count=question_count,
        graded_count=graded_count,
        coverage=coverage,
    )


def _build_response(a: Assessment, summary: AssessmentSummary | None = None) -> AssessmentResponse:
    return AssessmentResponse(
        id=a.id,
        name=a.name,
        description=a.description,
        created_at=a.created_at,
        updated_at=_effective_updated_at(a),
        question_set_updated_at=a.question_set_updated_at,
        rubric_updated_at=a.rubric_updated_at,
        source_updated_at=a.source_updated_at,
        results_updated_at=a.results_updated_at,
        summary=summary,
    )


class AssessmentService(BaseService):
    def __init__(
        self,
        repo: AssessmentRepository,
        memberships: MembershipRepository,
        submission_repo: SubmissionRepository | None = None,
    ) -> None:
        super().__init__(repo)
        self.memberships = memberships
        self.submission_repo = submission_repo

    def create(self, req: AssessmentCreateRequest, creator_user_id: str) -> AssessmentResponse:
        a = self.repo.create(req.name, req.description)
        self.memberships.add_member(creator_user_id, a.id, role="owner")
        return _build_response(a)

    def get(self, assessment_id: str) -> AssessmentResponse:
        return _build_response(self._get_or_404(assessment_id))

    def update(self, assessment_id: str, req: AssessmentUpdateRequest) -> AssessmentResponse:
        a = self._get_or_404(assessment_id)
        a = self.repo.update(a.id, req.name, req.description)
        return _build_response(a)

    def delete(self, assessment_id: str) -> None:
        self.repo.delete(self._get_or_404(assessment_id).id)

    def list_for_user(self, user_id: str) -> list[AssessmentResponse]:
        assessments = self.memberships.list_user_assessments(user_id)
        results: list[AssessmentResponse] = []
        for a in assessments:
            summary = _build_summary(a, self.submission_repo) if self.submission_repo else None
            results.append(_build_response(a, summary))
        return results
