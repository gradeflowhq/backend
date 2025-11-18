from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.question_sets import (
    InferQuestionSetRequest,
    ParseSubmissionsRequest,
    ParseSubmissionsResponse,
    QuestionSetResponse,
    SetQuestionSetByDataRequest,
    SetQuestionSetByModelRequest,
)
from gradeflow_backend.services.question_sets import QuestionSetService

router = APIRouter(prefix="/assessments/{assessment_id}/question-set", tags=["question_sets"])


def get_service(db: Session = Depends(get_session)) -> QuestionSetService:
    return QuestionSetService(AssessmentRepository(db))


@router.get("", response_model=QuestionSetResponse)
def get_question_set(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> QuestionSetResponse:
    return svc.get(assessment_id)


@router.put("", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def set_question_set_by_model(
    assessment_id: str,
    req: SetQuestionSetByModelRequest,
    svc: QuestionSetService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.set_by_model(assessment_id, req)


@router.put("/load", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def set_question_set_by_data(
    assessment_id: str,
    req: SetQuestionSetByDataRequest,
    svc: QuestionSetService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.set_by_data(assessment_id, req)


@router.post("/infer", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def infer_question_set(
    assessment_id: str,
    req: InferQuestionSetRequest,
    svc: QuestionSetService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.infer(assessment_id, req)


@router.post("/parse", response_model=ParseSubmissionsResponse, status_code=status.HTTP_200_OK)
def parse_submissions(
    assessment_id: str,
    req: ParseSubmissionsRequest,
    svc: QuestionSetService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> ParseSubmissionsResponse:
    return svc.parse(assessment_id, req)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_question_set(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete(assessment_id)
