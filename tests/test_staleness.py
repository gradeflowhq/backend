"""Unit tests for staleness utility functions."""

from datetime import UTC, datetime, timedelta

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.utils.staleness import question_set_status, results_status, rubric_status


def _make_assessment(**kwargs: object) -> Assessment:
    """Build a minimal Assessment-like object with controllable timestamps."""
    a = Assessment()
    defaults: dict[str, object] = {
        "id": "test-id",
        "name": "Test",
        "description": None,
        "question_set_yaml": None,
        "rubric_yaml": None,
        "source_data": None,
        "source_student_id_column": None,
        "submissions_config_yaml": None,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
        "source_updated_at": None,
        "question_set_updated_at": None,
        "rubric_updated_at": None,
        "results_updated_at": None,
        "user_links": [],
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(a, k, v)
    return a


T0 = datetime(2024, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T1 + timedelta(hours=1)
T3 = T2 + timedelta(hours=1)

MINIMAL_RUBRIC_YAML = "rules: []\n"
RUBRIC_WITH_RULES = """
rules:
  - type: TEXT_MATCH
    question_id: q1
    answers: ["A"]
    max_points: 1.0
"""


# ----- question_set_status -----


def test_qset_status_no_yaml_not_stale() -> None:
    a = _make_assessment(question_set_yaml=None)
    s = question_set_status(a)
    assert s.is_stale is False
    assert s.updated_at is None


def test_qset_status_no_source_update_not_stale() -> None:
    a = _make_assessment(
        question_set_yaml="question_map: {}",
        question_set_updated_at=T1,
        source_updated_at=None,
    )
    s = question_set_status(a)
    assert s.is_stale is False


def test_qset_status_source_newer_than_qset_is_stale() -> None:
    a = _make_assessment(
        question_set_yaml="question_map: {}",
        question_set_updated_at=T1,
        source_updated_at=T2,
    )
    s = question_set_status(a)
    assert s.is_stale is True


def test_qset_status_qset_newer_than_source_not_stale() -> None:
    a = _make_assessment(
        question_set_yaml="question_map: {}",
        question_set_updated_at=T2,
        source_updated_at=T1,
    )
    s = question_set_status(a)
    assert s.is_stale is False


# ----- rubric_status -----


def test_rubric_status_no_yaml_not_stale() -> None:
    a = _make_assessment(rubric_yaml=None)
    s = rubric_status(a)
    assert s.is_stale is False


def test_rubric_status_empty_rules_not_stale() -> None:
    """A rubric with no rules is never considered stale regardless of timestamps."""
    a = _make_assessment(
        rubric_yaml=MINIMAL_RUBRIC_YAML,
        rubric_updated_at=T1,
        question_set_updated_at=T3,  # would be stale if rules existed
        question_set_yaml="question_map: {}",
        source_updated_at=None,
    )
    s = rubric_status(a)
    assert s.is_stale is False


def test_rubric_status_qset_stale_propagates() -> None:
    """If the question set is stale, the rubric is also stale."""
    a = _make_assessment(
        rubric_yaml=RUBRIC_WITH_RULES,
        rubric_updated_at=T2,
        question_set_yaml="question_map: {}",
        question_set_updated_at=T1,
        source_updated_at=T2,  # source newer → qset stale
    )
    s = rubric_status(a)
    assert s.is_stale is True


def test_rubric_status_qset_newer_than_rubric_is_stale() -> None:
    a = _make_assessment(
        rubric_yaml=RUBRIC_WITH_RULES,
        rubric_updated_at=T1,
        question_set_yaml="question_map: {}",
        question_set_updated_at=T2,
        source_updated_at=None,
    )
    s = rubric_status(a)
    assert s.is_stale is True


def test_rubric_status_rubric_newer_than_qset_not_stale() -> None:
    a = _make_assessment(
        rubric_yaml=RUBRIC_WITH_RULES,
        rubric_updated_at=T3,
        question_set_yaml="question_map: {}",
        question_set_updated_at=T2,
        source_updated_at=T1,
    )
    s = rubric_status(a)
    assert s.is_stale is False


# ----- results_status -----


def test_results_status_no_results_not_stale() -> None:
    a = _make_assessment(
        results_updated_at=None,
        rubric_yaml=None,
    )
    s = results_status(a)
    assert s.is_stale is False
    assert s.updated_at is None


def test_results_status_rubric_newer_than_results_is_stale() -> None:
    a = _make_assessment(
        results_updated_at=T1,
        rubric_yaml=RUBRIC_WITH_RULES,
        rubric_updated_at=T2,
        question_set_yaml="question_map: {}",
        question_set_updated_at=T1,
        source_updated_at=None,
    )
    s = results_status(a)
    assert s.is_stale is True


def test_results_status_results_newer_than_rubric_not_stale() -> None:
    a = _make_assessment(
        results_updated_at=T3,
        rubric_yaml=RUBRIC_WITH_RULES,
        rubric_updated_at=T2,
        question_set_yaml="question_map: {}",
        question_set_updated_at=T1,
        source_updated_at=None,
    )
    s = results_status(a)
    assert s.is_stale is False
