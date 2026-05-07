from fastapi import APIRouter, Depends, status
from gradeflow_engine.rules.models import QuestionRule

from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.dependencies.services import get_rubric_service
from gradeflow_backend.schemas.rubrics import (
    RubricResponse,
    RuleCreateRequest,
    RulesResponse,
    RuleUpdateRequest,
)
from gradeflow_backend.services.rubrics import RubricService

router = APIRouter(prefix="/assessments/{assessment_id}/rules", tags=["rules"])


@router.get("", response_model=RulesResponse)
def list_rules(
    assessment_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(member_guard_factory()),
) -> RulesResponse:
    return svc.list_rules(assessment_id)


@router.post("", response_model=RubricResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    assessment_id: str,
    req: RuleCreateRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.create_rule(assessment_id, req)


@router.get("/{rule_id}", response_model=QuestionRule)
def get_rule(
    assessment_id: str,
    rule_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(member_guard_factory()),
) -> QuestionRule:
    return svc.get_rule(assessment_id, rule_id)


@router.put("/{rule_id}", response_model=RubricResponse, status_code=status.HTTP_200_OK)
def update_rule(
    assessment_id: str,
    rule_id: str,
    req: RuleUpdateRequest,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> RubricResponse:
    return svc.update_rule(assessment_id, rule_id, req)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    assessment_id: str,
    rule_id: str,
    svc: RubricService = Depends(get_rubric_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete_rule(assessment_id, rule_id)
