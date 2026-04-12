import csv
from io import StringIO

import yaml
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.submissions.models import RawSubmission

from gradeflow_backend.schemas.grading import GradingJobSpec
from gradeflow_backend.utils.renderers import (
    render_point_columns_map,
    render_question_set_yaml,
    render_rubric_yaml_minimal,
    render_submissions_csv,
)


def _make_spec(
    raw_submissions: list[RawSubmission] | None = None,
    point_columns: dict[str, str] | None = None,
) -> GradingJobSpec:
    if raw_submissions is None:
        raw_submissions = [
            RawSubmission(student_id="s1", raw_answer_map={"q1": "Alice", "q2": "90"}),
            RawSubmission(student_id="s2", raw_answer_map={"q1": "Bob"}),
        ]
    qset_yaml = """
question_map:
  q1:
    type: TEXT
    max_points: 1.0
  q2:
    type: NUMERIC
    max_points: 2.0
"""
    rubric_yaml = """
rules:
  - type: TEXT_MATCH
    question_id: q1
    answers: ["Alice"]
    max_points: 1.0
"""
    qset = QuestionSet.model_validate(yaml.safe_load(qset_yaml))
    rubric = Rubric.model_validate(yaml.safe_load(rubric_yaml))
    return GradingJobSpec(
        assessment_id="test-assessment",
        type="run",
        raw_submissions=raw_submissions,
        question_set=qset,
        rubric=rubric,
    )


def test_render_submissions_csv_header_contains_student_id() -> None:
    spec = _make_spec()
    csv_str = render_submissions_csv(spec)
    reader = csv.DictReader(StringIO(csv_str))
    assert "student_id" in (reader.fieldnames or [])


def test_render_submissions_csv_all_students_present() -> None:
    spec = _make_spec()
    csv_str = render_submissions_csv(spec)
    reader = csv.DictReader(StringIO(csv_str))
    rows = list(reader)
    student_ids = {r["student_id"] for r in rows}
    assert student_ids == {"s1", "s2"}


def test_render_submissions_csv_missing_answer_is_empty_string() -> None:
    spec = _make_spec()
    csv_str = render_submissions_csv(spec)
    reader = csv.DictReader(StringIO(csv_str))
    rows = {r["student_id"]: r for r in reader}
    # s2 has no q2
    assert rows["s2"]["q2"] == ""


def test_render_submissions_csv_question_ids_natsorted() -> None:
    subs = [RawSubmission(student_id="s1", raw_answer_map={"q10": "x", "q2": "y", "q1": "z"})]
    spec = _make_spec(raw_submissions=subs)
    csv_str = render_submissions_csv(spec)
    reader = csv.DictReader(StringIO(csv_str))
    fields = list(reader.fieldnames or [])
    q_fields = [f for f in fields if f.startswith("q")]
    assert q_fields == sorted(q_fields, key=lambda x: (len(x), x))  # natsort: q1 < q2 < q10


def test_render_point_columns_map_empty_when_no_result_map() -> None:
    spec = _make_spec()
    mapping = render_point_columns_map(spec)
    assert mapping == {}


def test_render_point_columns_map_with_passthrough_results() -> None:
    from gradeflow_engine.rules.result import QuestionResult

    subs = [
        RawSubmission(
            student_id="s1",
            raw_answer_map={"q1": "Alice"},
            result_map={
                "q1": QuestionResult(
                    output=1.0, passed=True, feedback="ok", rule="r", points=1.0, max_points=1.0
                )
            },
        )
    ]
    spec = _make_spec(raw_submissions=subs)
    mapping = render_point_columns_map(spec)
    assert "q1" in mapping
    assert mapping["q1"].startswith("__pts_")


def test_render_question_set_yaml_is_valid_yaml() -> None:
    spec = _make_spec()
    qs_yaml = render_question_set_yaml(spec)
    parsed = yaml.safe_load(qs_yaml)
    assert isinstance(parsed, dict)


def test_render_rubric_yaml_minimal_strips_engine_fields() -> None:
    spec = _make_spec()
    rubric_yaml = render_rubric_yaml_minimal(spec)
    parsed = yaml.safe_load(rubric_yaml)
    assert isinstance(parsed, dict)

    # Engine-internal fields must not appear
    def _has_engine_field(obj: object) -> bool:
        if isinstance(obj, dict):
            if "question_types" in obj or "constraints" in obj:
                return True
            return any(_has_engine_field(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_has_engine_field(i) for i in obj)
        return False

    assert not _has_engine_field(parsed)


def test_render_submissions_csv_deterministic() -> None:
    """Two calls with the same spec must produce identical output."""
    spec = _make_spec()
    assert render_submissions_csv(spec) == render_submissions_csv(spec)
