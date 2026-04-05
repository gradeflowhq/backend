from fastapi import APIRouter, Depends, status

from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.dependencies.services import get_submissions_service
from gradeflow_backend.schemas.submissions import (
    SourceDataResponse,
    SubmissionsImportConfig,
    SubmissionsResponse,
    UploadSourceDataRequest,
)
from gradeflow_backend.services.submissions import SubmissionsService

router = APIRouter(prefix="/assessments/{assessment_id}/submissions", tags=["submissions"])


@router.put("/source", response_model=SourceDataResponse, status_code=status.HTTP_200_OK)
def upload_source_data(
    assessment_id: str,
    req: UploadSourceDataRequest,
    svc: SubmissionsService = Depends(get_submissions_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> SourceDataResponse:
    return svc.upload_source_data(assessment_id, req)


@router.get("/source", response_model=SourceDataResponse)
def get_source_data(
    assessment_id: str,
    svc: SubmissionsService = Depends(get_submissions_service),
    _u: str = Depends(member_guard_factory()),
) -> SourceDataResponse:
    return svc.get_source_data(assessment_id)


@router.put("/config", response_model=SubmissionsImportConfig, status_code=status.HTTP_200_OK)
def save_import_config(
    assessment_id: str,
    req: SubmissionsImportConfig,
    svc: SubmissionsService = Depends(get_submissions_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> SubmissionsImportConfig:
    return svc.save_import_config(assessment_id, req)


@router.get("/config", response_model=SubmissionsImportConfig)
def get_import_config(
    assessment_id: str,
    svc: SubmissionsService = Depends(get_submissions_service),
    _u: str = Depends(member_guard_factory()),
) -> SubmissionsImportConfig:
    return svc.get_import_config(assessment_id)


@router.get("", response_model=SubmissionsResponse)
def get_submissions(
    assessment_id: str,
    svc: SubmissionsService = Depends(get_submissions_service),
    _u: str = Depends(member_guard_factory()),
) -> SubmissionsResponse:
    return svc.get(assessment_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_submissions(
    assessment_id: str,
    svc: SubmissionsService = Depends(get_submissions_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete(assessment_id)
