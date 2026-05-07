from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from gradeflow_backend.dependencies.auth import get_current_user_id
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.dependencies.services import get_assessment_service
from gradeflow_backend.schemas.assessments import (
    METADATA_KEY_PATTERN,
    AssessmentCreateRequest,
    AssessmentMetadataRequest,
    AssessmentMetadataResponse,
    AssessmentMetadataValueRequest,
    AssessmentMetadataValueResponse,
    AssessmentResponse,
    AssessmentsListResponse,
    AssessmentUpdateRequest,
)
from gradeflow_backend.services.assessments import AssessmentService

router = APIRouter(prefix="/assessments", tags=["assessments"])
MetadataKey = Annotated[
    str,
    Path(min_length=1, max_length=128, pattern=METADATA_KEY_PATTERN),
]


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    req: AssessmentCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    svc: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    return svc.create(req, creator_user_id=current_user_id)


@router.get("", response_model=AssessmentsListResponse)
def list_assessments(
    current_user_id: str = Depends(get_current_user_id),
    svc: AssessmentService = Depends(get_assessment_service),
) -> AssessmentsListResponse:
    return AssessmentsListResponse(items=svc.list_for_user(current_user_id))


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: str,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(member_guard_factory()),
) -> AssessmentResponse:
    return svc.get(assessment_id)


@router.patch("/{assessment_id}", response_model=AssessmentResponse)
def update_assessment(
    assessment_id: str,
    req: AssessmentUpdateRequest,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(role_guard_factory("owner")),
) -> AssessmentResponse:
    return svc.update(assessment_id, req)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: str,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(role_guard_factory("owner")),
) -> None:
    svc.delete(assessment_id)


@router.get("/{assessment_id}/metadata", response_model=AssessmentMetadataResponse)
def get_assessment_metadata(
    assessment_id: str,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(member_guard_factory()),
) -> AssessmentMetadataResponse:
    return svc.get_metadata(assessment_id)


@router.put("/{assessment_id}/metadata", response_model=AssessmentMetadataResponse)
def replace_assessment_metadata(
    assessment_id: str,
    req: AssessmentMetadataRequest,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(role_guard_factory("editor")),
) -> AssessmentMetadataResponse:
    return svc.replace_metadata(assessment_id, req)


@router.get(
    "/{assessment_id}/metadata/{key}",
    response_model=AssessmentMetadataValueResponse,
)
def get_assessment_metadata_value(
    assessment_id: str,
    key: MetadataKey,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(member_guard_factory()),
) -> AssessmentMetadataValueResponse:
    return svc.get_metadata_value(assessment_id, key)


@router.put(
    "/{assessment_id}/metadata/{key}",
    response_model=AssessmentMetadataValueResponse,
)
def set_assessment_metadata_value(
    assessment_id: str,
    key: MetadataKey,
    req: AssessmentMetadataValueRequest,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(role_guard_factory("editor")),
) -> AssessmentMetadataValueResponse:
    return svc.set_metadata_value(assessment_id, key, req)


@router.delete("/{assessment_id}/metadata/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment_metadata_value(
    assessment_id: str,
    key: MetadataKey,
    svc: AssessmentService = Depends(get_assessment_service),
    _user: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete_metadata_value(assessment_id, key)
