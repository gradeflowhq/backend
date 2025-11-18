from fastapi import APIRouter
from gradeflow_engine.core import (
    list_available_question_set_loaders,
    list_available_question_set_savers,
    list_available_rubric_loaders,
    list_available_submissions_loaders,
    list_available_submissions_savers,
)

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("/question-set-loaders")
def question_set_loaders() -> list[str]:
    return list_available_question_set_loaders()


@router.get("/question-set-savers")
def question_set_savers() -> list[str]:
    return list_available_question_set_savers()


@router.get("/rubric-loaders")
def rubric_loaders() -> list[str]:
    return list_available_rubric_loaders()


@router.get("/submissions-loaders")
def submissions_loaders() -> list[str]:
    return list_available_submissions_loaders()


@router.get("/submissions-savers")
def submissions_savers() -> list[str]:
    return list_available_submissions_savers()
