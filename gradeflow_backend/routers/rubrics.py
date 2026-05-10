from fastapi import APIRouter, Depends, status

from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.dependencies.services import get_rubric_service
from gradeflow_backend.schemas.rubrics import (
    ExportRubricRequest,
    ExportRubricResponse,
    ImportRubricRequest,
    LoadRubricRequest,
    RubricOverviewResponse,
    RubricResponse,
    SetRubricByModelRequest,
    ValidateRubricRequest,
    ValidateRubricResponse,
)
from gradeflow_backend.services.rubrics import RubricService

router = APIRouter(prefix="/assessments/{assessment_id}/rubric", tags=["rubrics"])


@router.get("", response_model=RubricResponse)
def get_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(member_guard_factory()),
) -> RubricResponse:
    return svc.get(assessment_id)


@router.post("/export", response_model=ExportRubricResponse, status_code=status.HTTP_200_OK)
def export_rubric(
    assessment_id: str,
    req: ExportRubricRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(member_guard_factory()),
) -> ExportRubricResponse:
    return svc.export(assessment_id, req)


@router.put("", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def set_rubric_by_model(
    assessment_id: str,
    req: SetRubricByModelRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.set_by_model(assessment_id, req)


@router.put("/upload", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def set_rubric_by_data(
    assessment_id: str,
    req: LoadRubricRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.set_by_data(assessment_id, req)


@router.put("/import", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def import_rubric(
    assessment_id: str,
    req: ImportRubricRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.set_by_adapter(assessment_id, req)


@router.post("/empty", response_model=RubricResponse, status_code=status.HTTP_201_CREATED)
def create_empty_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.create_empty_rubric(assessment_id)


@router.post(
    "/staleness/acknowledge",
    response_model=RubricResponse,
    status_code=status.HTTP_200_OK,
)
def acknowledge_rubric_staleness(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.acknowledge_rubric_staleness(assessment_id)


@router.post("/validate", response_model=ValidateRubricResponse, status_code=status.HTTP_200_OK)
def validate_rubric(
    assessment_id: str,
    req: ValidateRubricRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(member_guard_factory()),
) -> ValidateRubricResponse:
    return svc.validate(assessment_id, req)


@router.post("/sync", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def sync_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.sync_stale_rules(assessment_id)


@router.post("/repair", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def repair_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.repair(assessment_id)


@router.get("/overview", response_model=RubricOverviewResponse, status_code=status.HTTP_200_OK)
def rubric_overview(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(member_guard_factory()),
) -> RubricOverviewResponse:
    return svc.overview(assessment_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete(assessment_id)
