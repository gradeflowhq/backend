from gradeflow_engine.core import load_question_set_from_blob, load_rubric_from_blob
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.services.exceptions import NotFoundError
from gradeflow_backend.utils.io import blob_from_str

_YAML_BLOB_KWARGS = {"media_type": "application/yaml", "ext": "yaml"}


def load_rubric(a: Assessment, *, strict: bool = True) -> Rubric:
    """
    Load the persisted rubric for an assessment.

    Raises:
        NotFoundError: If no rubric YAML is stored on the assessment.
    """
    if not a.rubric_yaml:
        raise NotFoundError("Rubric not set")
    return load_rubric_from_blob(
        blob_from_str(a.rubric_yaml, **_YAML_BLOB_KWARGS),
        serializer_name="yaml",
        strict=strict,
    )


def load_question_set(a: Assessment) -> QuestionSet:
    """
    Load the persisted question set for an assessment.

    Raises:
        NotFoundError: If no question set YAML is stored on the assessment.
    """
    if not a.question_set_yaml:
        raise NotFoundError("Question set not set")
    return load_question_set_from_blob(
        blob_from_str(a.question_set_yaml, **_YAML_BLOB_KWARGS),
        serializer_name="yaml",
    )
