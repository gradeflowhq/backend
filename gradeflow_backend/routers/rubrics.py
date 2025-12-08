from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.rubrics import (
    CoverageRequest,
    CoverageResponse,
    ImportRubricRequest,
    LoadRubricRequest,
    RubricResponse,
    SetRubricByModelRequest,
    ValidateRubricRequest,
    ValidateRubricResponse,
)
from gradeflow_backend.services.rubrics import RubricService

router = APIRouter(prefix="/assessments/{assessment_id}/rubric", tags=["rubrics"])


def get_service(db: Session = Depends(get_session)) -> RubricService:
    return RubricService(AssessmentRepository(db))


@router.get("", response_model=RubricResponse)
def get_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> RubricResponse:
    return svc.get(assessment_id)


@router.put("", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def set_rubric_by_model(
    assessment_id: str,
    req: SetRubricByModelRequest,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.set_by_model(assessment_id, req)


@router.put("/upload", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def set_rubric_by_data(
    assessment_id: str,
    req: LoadRubricRequest,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.set_by_data(assessment_id, req)


@router.put("/import", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def import_rubric(
    assessment_id: str,
    req: ImportRubricRequest,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.set_by_adapter(assessment_id, req)


@router.post("/validate", response_model=ValidateRubricResponse, status_code=status.HTTP_200_OK)
def validate_rubric(
    assessment_id: str,
    req: ValidateRubricRequest,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> ValidateRubricResponse:
    return svc.validate(assessment_id, req)


@router.post("/coverage", response_model=CoverageResponse, status_code=status.HTTP_200_OK)
def rubric_coverage(
    assessment_id: str,
    req: CoverageRequest,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> CoverageResponse:
    return svc.coverage(assessment_id, req)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete(assessment_id)
