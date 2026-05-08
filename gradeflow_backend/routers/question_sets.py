from fastapi import APIRouter, Depends, status
from gradeflow_engine.questions.models import Question

from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.dependencies.services import get_question_set_service
from gradeflow_backend.schemas.question_sets import (
    ExportQuestionSetRequest,
    ExportQuestionSetResponse,
    ImportQuestionSetRequest,
    InferQuestionSetRequest,
    LoadQuestionSetRequest,
    ParseSubmissionsRequest,
    ParseSubmissionsResponse,
    QuestionCreateRequest,
    QuestionSetResponse,
    QuestionSetStatusResponse,
    QuestionUpdateRequest,
    SetQuestionSetByModelRequest,
)
from gradeflow_backend.services.question_sets import QuestionSetService

router = APIRouter(prefix="/assessments/{assessment_id}/question-set", tags=["question_sets"])


@router.get("", response_model=QuestionSetResponse)
def get_question_set(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(member_guard_factory()),
) -> QuestionSetResponse:
    return svc.get(assessment_id)


@router.get("/status", response_model=QuestionSetStatusResponse)
def get_question_set_status(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(member_guard_factory()),
) -> QuestionSetStatusResponse:
    return svc.get_status(assessment_id)


@router.post("/sync", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def sync_question_set(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.sync(assessment_id)


@router.post(
    "/staleness/acknowledge",
    response_model=QuestionSetResponse,
    status_code=status.HTTP_200_OK,
)
def acknowledge_question_set_staleness(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.acknowledge_question_set_staleness(assessment_id)


@router.post("/export", response_model=ExportQuestionSetResponse, status_code=status.HTTP_200_OK)
def export_question_set(
    assessment_id: str,
    req: ExportQuestionSetRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(member_guard_factory()),
) -> ExportQuestionSetResponse:
    return svc.export(assessment_id, req)


@router.put("", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def set_question_set_by_model(
    assessment_id: str,
    req: SetQuestionSetByModelRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.set_by_model(assessment_id, req)


@router.put("/upload", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def set_question_set_by_data(
    assessment_id: str,
    req: LoadQuestionSetRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.set_by_data(assessment_id, req)


@router.put("/import", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def import_question_set(
    assessment_id: str,
    req: ImportQuestionSetRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.set_by_adapter(assessment_id, req)


@router.post("/infer", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK)
def infer_question_set(
    assessment_id: str,
    req: InferQuestionSetRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.infer(assessment_id, req)


@router.post("/parse", response_model=ParseSubmissionsResponse, status_code=status.HTTP_200_OK)
def parse_submissions(
    assessment_id: str,
    req: ParseSubmissionsRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(member_guard_factory()),
) -> ParseSubmissionsResponse:
    return svc.parse(assessment_id, req)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_question_set(
    assessment_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete(assessment_id)


@router.post("/questions", response_model=QuestionSetResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    assessment_id: str,
    req: QuestionCreateRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.create_question(assessment_id, req)


@router.get("/questions/{question_id}", response_model=Question)
def get_question(
    assessment_id: str,
    question_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(member_guard_factory()),
) -> Question:
    return svc.get_question(assessment_id, question_id)


@router.put(
    "/questions/{question_id}", response_model=QuestionSetResponse, status_code=status.HTTP_200_OK
)
def update_question(
    assessment_id: str,
    question_id: str,
    req: QuestionUpdateRequest,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> QuestionSetResponse:
    return svc.update_question(assessment_id, question_id, req)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    assessment_id: str,
    question_id: str,
    svc: QuestionSetService = Depends(get_question_set_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete_question(assessment_id, question_id)
