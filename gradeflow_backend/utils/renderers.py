from __future__ import annotations

import csv
from io import StringIO

import yaml
from natsort import natsorted

from gradeflow_backend.schemas.grading import GradingJobSpec
from gradeflow_backend.utils.engine import model_dump_minimal

_POINT_COL_PREFIX = "__pts_"


def render_point_columns_map(spec: GradingJobSpec) -> dict[str, str]:
    """
    Returns {qid: csv_col_name} for every question that has a passthrough result_map
    entry in any of the raw submissions.  Column names use the ``__pts_`` prefix so
    they cannot collide with real answer columns.
    """
    qids: set[str] = set()
    for rs in spec.raw_submissions:
        qids.update(rs.result_map.keys())
    return {qid: f"{_POINT_COL_PREFIX}{qid}" for qid in natsorted(qids)}


def render_submissions_csv(spec: GradingJobSpec) -> str:
    """
    Deterministic CSV for RawSubmission list:
      - Columns: student_id + union of all question IDs (natsorted) + __pts_<qid> for any
        pre-populated passthrough result_map entries
      - Rows: one per RawSubmission, missing answers serialized as empty string
    Mirrors logic used by in-memory executor to ensure consistent ordering.
    """
    qids: set[str] = set()
    for rs in spec.raw_submissions:
        qids.update(rs.raw_answer_map.keys())
    ordered_qids = natsorted(qids)

    point_cols = render_point_columns_map(spec)  # {qid: col_name}

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=["student_id", *ordered_qids, *point_cols.values()])
    writer.writeheader()
    for rs in spec.raw_submissions:
        row: dict[str, str] = {"student_id": rs.student_id}
        for qid in ordered_qids:
            row[qid] = rs.raw_answer_map.get(qid, "")
        for qid, col in point_cols.items():
            result = rs.result_map.get(qid)
            row[col] = str(result.points) if result is not None else ""
        writer.writerow(row)
    return buf.getvalue()


def render_question_set_yaml(spec: GradingJobSpec) -> str:
    """
    YAML dump of QuestionSet using model_dump (no internal fields added).
    """
    return yaml.safe_dump(spec.question_set.model_dump(), sort_keys=False)


def render_rubric_yaml_minimal(spec: GradingJobSpec) -> str:
    """
    Minimal YAML dump of Rubric, stripping engine-internal fields via model_dump_minimal.
    Matches how RubricService/JobsService persist rubrics for engine consumption.
    """
    return yaml.safe_dump(model_dump_minimal(spec.rubric), sort_keys=False)
