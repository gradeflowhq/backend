from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.services.exceptions import NotFoundError


class BaseService:
    """
    Shared base for all assessment-scoped services.

    Provides the canonical ``_get_or_404`` guard so every subclass
    gets consistent error handling without repeating the try/except.
    """

    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def _get_or_404(self, assessment_id: str) -> Assessment:
        try:
            return self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
