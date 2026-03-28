from fastapi import APIRouter
from gradeflow_engine.core import (
    list_available_question_set_adapters,
    # Serializers
    list_available_question_set_serializers,
    # Adapters
    list_available_raw_submissions_adapters,
    list_available_rubric_adapters,
    list_available_rubric_serializers,
    list_available_submissions_serializers,
)

router = APIRouter(prefix="/registry", tags=["registry"])

# ---------------------------
# Serializers
# ---------------------------


@router.get("/serializers/question-sets")
def question_set_serializers() -> list[str]:
    return list_available_question_set_serializers()


@router.get("/serializers/rubrics")
def rubric_serializers() -> list[str]:
    return list_available_rubric_serializers()


@router.get("/serializers/submissions")
def submissions_serializers() -> list[str]:
    return list_available_submissions_serializers()


# ---------------------------
# Adapters
# ---------------------------


@router.get("/adapters/raw-submissions")
def raw_submissions_adapters() -> list[str]:
    return list_available_raw_submissions_adapters()


@router.get("/adapters/question-sets")
def question_set_adapters() -> list[str]:
    return list_available_question_set_adapters()


@router.get("/adapters/rubrics")
def rubric_adapters() -> list[str]:
    return list_available_rubric_adapters()
