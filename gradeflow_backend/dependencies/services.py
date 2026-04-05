"""
Centralised FastAPI dependency factories for all services.

Keeping these here means each router only imports the function it needs,
and the wiring between repositories, sessions, and services is defined
in exactly one place.
"""

import valkey
from fastapi import Depends
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session, get_valkey
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.grading_jobs import GradingJobRepository
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.repositories.submissions import SubmissionRepository
from gradeflow_backend.repositories.tokens import RefreshTokenRepository
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.services.assessments import AssessmentService
from gradeflow_backend.services.auth import AuthService
from gradeflow_backend.services.grading import GradingService
from gradeflow_backend.services.jobs import JobsService
from gradeflow_backend.services.memberships import MembershipService
from gradeflow_backend.services.question_sets import QuestionSetService
from gradeflow_backend.services.rubrics import RubricService
from gradeflow_backend.services.submissions import SubmissionsService


def get_auth_service(db: Session = Depends(get_session)) -> AuthService:
    return AuthService(UserRepository(db), RefreshTokenRepository(db))


def get_assessment_service(db: Session = Depends(get_session)) -> AssessmentService:
    return AssessmentService(AssessmentRepository(db), MembershipRepository(db))


def get_submissions_service(db: Session = Depends(get_session)) -> SubmissionsService:
    return SubmissionsService(AssessmentRepository(db))


def get_question_set_service(db: Session = Depends(get_session)) -> QuestionSetService:
    return QuestionSetService(AssessmentRepository(db))


def get_rubric_service(db: Session = Depends(get_session)) -> RubricService:
    return RubricService(AssessmentRepository(db))


def get_grading_service(
    db: Session = Depends(get_session),
    valkey_client: valkey.Valkey = Depends(get_valkey),
) -> GradingService:
    return GradingService(
        AssessmentRepository(db, valkey_client),
        GradingJobRepository(db),
        SubmissionRepository(db),
    )


def get_jobs_service(
    db: Session = Depends(get_session),
    valkey_client: valkey.Valkey = Depends(get_valkey),
) -> JobsService:
    return JobsService(db, valkey_client)


def get_membership_service(db: Session = Depends(get_session)) -> MembershipService:
    return MembershipService(MembershipRepository(db), UserRepository(db))
